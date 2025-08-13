import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard'; // Default import
import ComplaintDetail from './pages/ComplaintDetail';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/complaint/:id" element={<ComplaintDetail />} />
        <Route path="/" element={<Login />} />
      </Routes>
    </Router>
  );
}

export default App;