// Farmer-facing app with its fonts and styles (its own chunk, see main.jsx).
// Self-hosted font (bundled by Vite into /assets): the CSP blocks external fonts.
import '@fontsource/atkinson-hyperlegible/latin-400.css';
import '@fontsource/atkinson-hyperlegible/latin-700.css';
import './styles/tokens.css';
import './styles/app.css';
import App from './App.jsx';

export default App;
