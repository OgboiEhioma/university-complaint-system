import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';

function ComplaintDetail() {
  const { id } = useParams();
  const [complaint, setComplaint] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    async function fetchComplaint() {
      try {
        const response = await api.get(`/complaints/${id}`);
        setComplaint(response.data);
      } catch (error) {
        navigate('/dashboard');
      }
    }
    fetchComplaint();
  }, [id]);

  if (!complaint) return <div>Loading...</div>;

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-3xl font-bold mb-6">{complaint.title}</h1>
      <p>{complaint.description}</p>
      <p>Status: {complaint.status}</p>
      {/* Add delete if allowed: <button onClick={async () => { await api.delete(`/complaints/${id}`); navigate('/dashboard'); }}>Delete</button> */}
    </div>
  );
}

export default ComplaintDetail;