from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.bdns.importer import (
    BDNSImportError,
    classify_search_activity,
    flatten_region_catalog,
    import_calls,
    map_call_record,
)
from app.bdns.change_detection import payload_sha256
from app.db.database import upsert_bdns_calls


@pytest.fixture
def aragon_detail():
    return {
        "id": 1122319,
        "codigoBDNS": "920758",
        "descripcion": "Farm support record",
        "descripcionLeng": None,
        "fechaRecepcion": "2026-07-22",
        "tipoConvocatoria": "Concesión directa",
        "presupuestoTotal": 200000,
        "mrr": False,
        "organo": {"nivel1": "AUTONOMICA", "nivel2": "ARAGÓN", "nivel3": "Agriculture Department"},
        "sedeElectronica": "https://example.es/apply",
        "instrumentos": [{"descripcion": "Grant"}],
        "tiposBeneficiarios": [{"descripcion": "Farmers"}],
        "sectores": [{"codigo": "A", "descripcion": "Agriculture"}],
        "regiones": [{"descripcion": "ES24 - ARAGON"}],
        "descripcionFinalidad": "Agriculture",
        "descripcionBasesReguladoras": "Rules",
        "urlBasesReguladoras": "https://example.es/rules.pdf",
        "fechaInicioSolicitud": None,
        "fechaFinSolicitud": None,
        "textInicio": "No deadline",
        "textFin": "No deadline",
        "abierto": False,
        "sePublicaDiarioOficial": False,
        "documentos": [{"id": 10, "nombreFic": "rules.pdf", "long": 123}],
        "anuncios": [],
        "fondos": [],
        "objetivos": [],
        "sectoresProductos": [],
    }


def test_maps_call_to_metadata_only_canonical_record(aragon_detail):
    record = map_call_record(aragon_detail, datetime(2026, 11, 11, tzinfo=timezone.utc))
    assert record["source_identity"]["bdns_code"] == "920758"
    assert record["call"]["territories"][0]["code"] == "ES24"
    assert record["call"]["farm_activity_classification"]["status"] == "unclassified"
    assert record["quality"]["reliability"] == "metadata_only"
    assert record["application"]["status"] == "unknown"
    assert record["sources"]["documents"][0]["download_url"].endswith("idDocumento=10")
    assert record["source_payload"] == aragon_detail
    assert record["source_state"]["payload_sha256"] == payload_sha256(aragon_detail)


@pytest.mark.parametrize("payload", [{}, {"codigoBDNS": "1"}, {"codigoBDNS": "1", "descripcion": "x", "regiones": {}}])
def test_rejects_missing_identity_title_or_invalid_shapes(payload):
    with pytest.raises(BDNSImportError):
        map_call_record(payload)


def test_bounded_aragon_import_deduplicates_search_terms_and_upserts_once(aragon_detail):
    class FakeClient:
        def __init__(self):
            self.queries = []
            self.details = []

        def iter_search(self, filters, *, max_pages, page_size):
            self.queries.append((filters, max_pages, page_size))
            return iter([
                {"numeroConvocatoria": "920758"},
                {"numeroConvocatoria": "920759"},
            ] if len(self.queries) == 1 else [
                {"numeroConvocatoria": "920758"},
            ])

        def get_call(self, code):
            self.details.append(code)
            result = deepcopy(aragon_detail)
            result["codigoBDNS"] = code
            result["descripcion"] = f"Call {code}"
            return result

    client = FakeClient()
    upserts = []
    commits = []
    observations = []
    class FakeConnection:
        def commit(self):
            commits.append(True)

    conn = FakeConnection()
    # The import function commits the supplied connection after its single batch upsert.
    records = import_calls(
        client,
        conn,
        regions=(21,),
        search_terms=("agricultura", "ganadería"),
        max_pages=1,
        page_size=10,
        upsert=lambda db_conn, values: upserts.append((db_conn, values)),
        query_observations=observations,
    )
    assert client.details == ["920758", "920759"]
    assert [record["source_identity"]["bdns_code"] for record in records] == ["920758", "920759"]
    assert len(upserts) == 1 and upserts[0][0] is conn
    assert commits == [True]
    assert all(record["quality"]["reliability"] == "metadata_only" for record in upserts[0][1])
    assert [(item["activity_scope"], item["candidate_count"], item["indexed_call_count"])
            for item in observations] == [("agriculture", 2, 2), ("livestock", 1, 1)]


def test_flattens_official_region_tree_and_labels_only_search_intent():
    regions = flatten_region_catalog([{
        "id": 21, "descripcion": "ES24 - ARAGÓN", "children": [
            {"id": 22, "descripcion": "ES241 - Huesca", "children": []},
        ],
    }])
    assert regions == [
        {"region_id": 21, "description": "ES24 - ARAGÓN", "nuts_code": "ES24",
         "parent_region_id": None, "depth": 0},
        {"region_id": 22, "description": "ES241 - Huesca", "nuts_code": "ES241",
         "parent_region_id": 21, "depth": 1},
    ]
    assert classify_search_activity("PAC") == "unknown"
    assert classify_search_activity("agricultura y ganadería") == "mixed"


def test_import_queries_each_region_separately_for_auditable_coverage(aragon_detail):
    queried_regions = []

    class FakeClient:
        def iter_search(self, filters, *, max_pages, page_size):
            queried_regions.append(filters.regions)
            return iter([{"numeroConvocatoria": "920758"}])

        def get_call(self, code):
            return aragon_detail

    observations = []
    records = import_calls(
        FakeClient(), None, regions=(21, 22), search_terms=("ganadería",),
        max_pages=1, query_observations=observations,
    )
    assert len(records) == 1
    assert queried_regions == [(21,), (22,)]
    assert [item["region_id"] for item in observations] == [21, 22]
    assert all(item["indexed_call_count"] == 0 for item in observations)


def test_dry_run_mapping_does_not_upsert(aragon_detail):
    class FakeClient:
        def iter_search(self, filters, *, max_pages, page_size):
            return iter([{"numeroConvocatoria": "920758"}])

        def get_call(self, code):
            return aragon_detail

    records = import_calls(
        FakeClient(), None, regions=(21,), search_terms=("agricultura",), max_pages=1
    )
    assert len(records) == 1


def test_storage_upserts_on_bdns_code_and_preserves_first_seen(aragon_detail):
    record = map_call_record(aragon_detail)

    class RecordingConnection:
        def __init__(self):
            self.statements = []

        def execute(self, statement, params):
            self.statements.append((statement, params))
            class EmptyResult:
                def fetchone(self):
                    return None

                def fetchall(self):
                    return []
            return EmptyResult()

    conn = RecordingConnection()
    upsert_bdns_calls(conn, [record])
    call_insert = next((item for item in conn.statements if "INSERT INTO bdns_calls" in item[0]), None)
    assert call_insert is not None
    assert "ON CONFLICT (bdns_code) DO UPDATE" in call_insert[0]
    assert "last_seen_at = now()" in call_insert[0]
    assert "first_seen_at =" not in call_insert[0]
    assert call_insert[1][0] == "920758"
    assert call_insert[1][2] == "metadata_only"
