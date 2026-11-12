from app.bdns.extraction import _extract_pdf_pages, _pdf_facts, extract_call_facts


def test_extracts_metadata_fields_without_changing_source_reliability():
    record = {
        "source_identity": {
            "bdns_code": "123", "detail_url": "https://bdns.example/call/123"
        },
        "source_state": {"payload_sha256": "a" * 64},
        "call": {
            "purpose": {"label": "Modernización de explotaciones"},
            "objectives": [],
            "beneficiary_categories": [{"label": "Personas físicas"}],
        },
        "application": {
            "start_date": "2026-02-01", "end_date": "2026-03-01",
            "start_text": None, "end_text": "Hasta el 1 de marzo", "open_ended": False,
            "application_portal_url": "https://example.es/solicitud",
        },
        "sources": {"documents": [{"bdns_document_id": 9, "filename": "bases.pdf",
                                      "download_url": "https://example.es/bases.pdf"}]},
        "quality": {"reliability": "metadata_only"},
    }

    result = extract_call_facts(record, [])

    assert result["reliability"] == "extracted"
    assert result["facts"]["purpose"][0]["value"] == "Modernización de explotaciones"
    assert result["facts"]["beneficiaries"][0]["value"] == "Personas físicas"
    assert result["facts"]["deadlines"]
    assert result["facts"]["documents"][0]["document_id"] == 9
    assert result["facts"]["application_route"][0]["value"] == "https://example.es/solicitud"
    assert result["facts"]["requirements"] == []
    assert result["facts"]["purpose"][0]["citation"] == {
        "url": "https://bdns.example/call/123",
        "page": None,
        "section": "call.purpose.label",
        "quote": "Modernización de explotaciones",
    }
    assert all(
        fact["citation"]["url"]
        and (fact["citation"]["page"] or fact["citation"]["section"])
        for candidates in result["facts"].values()
        for fact in candidates
    )
    assert record["quality"]["reliability"] == "metadata_only"
    assert result["field_status"]["requirements"] == "not_found"


def test_pdf_candidates_keep_page_and_document_location():
    pages = [{
        "document_id": 42,
        "source_url": "https://bdns.example/documents/42.pdf",
        "page": 7,
        "text": "El plazo de presentación de solicitudes finalizará el 15 de mayo. "
                "La sede electrónica habilitará el formulario.",
    }]

    facts = _pdf_facts(pages)

    assert facts["deadlines"][0]["document_id"] == 42
    assert facts["deadlines"][0]["page"] == 7
    assert "plazo de presentación" in facts["deadlines"][0]["quote"]
    assert facts["application_route"][0]["page"] == 7
    assert facts["deadlines"][0]["citation"] == {
        "url": "https://bdns.example/documents/42.pdf",
        "page": 7,
        "section": None,
        "quote": facts["deadlines"][0]["quote"],
    }


def test_unreadable_pdf_is_reported_without_raising():
    pages, error = _extract_pdf_pages(b"not a pdf", 1, "https://bdns.example/documents/1.pdf")

    assert pages == []
    assert error == "unreadable_pdf"
