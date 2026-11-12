import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// /review is the team's internal BDNS review tool; everything else is the farmer app.
// Each one loads its own code and CSS so their styles never mix.
const isReview = window.location.pathname.replace(/\/+$/, '') === '/review';
const load = isReview ? import('./review/ReviewApp.jsx') : import('./ChatEntry.jsx');

load.then(({ default: Root }) => {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <Root />
    </StrictMode>,
  );
});
