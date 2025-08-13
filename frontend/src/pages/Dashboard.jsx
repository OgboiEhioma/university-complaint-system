import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api';

function Dashboard() {
  const [complaints, setComplaints] = useState([]);
  const { register, handleSubmit, reset } = useForm();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem('user'));

  useEffect(() => {
    fetchComplaints();
  }, []);

  const fetchComplaints = async () => {
    try {
      const response = await api.get('/complaints'); // Original endpoint causing 404
      setComplaints(response.data);
    } catch (error) {
      if (error.response?.status === 401) navigate('/login');
      console.error('Error fetching complaints:', error);
    }
  };

  const onSubmit = async (data) => {
    try {
      await api.post('/complaints', data);
      reset();
      fetchComplaints();
    } catch (error) {
      alert('Submit failed: ' + (error.response?.data?.message || error.message));
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="flex justify-between mb-6">
        <h1 className="text-3xl font-bold">Complaint Dashboard</h1>
        <button onClick={handleLogout} className="bg-red-500 text-white p-2 rounded">Logout</button>
      </div>
      <form onSubmit={handleSubmit(onSubmit)} className="bg-white p-6 rounded shadow-md mb-6">
        <h2 className="text-xl font-bold mb-4">Submit Complaint</h2>
        <input {...register('title')} placeholder="Title" className="w-full p-2 mb-4 border rounded" required />
        <textarea {...register('description')} placeholder="Description" className="w-full p-2 mb-4 border rounded" required />
        <button type="submit" className="bg-blue-500 text-white p-2 rounded">Submit</button>
      </form>
      <div className="bg-white p-6 rounded shadow-md">
        <h2 className="text-xl font-bold mb-4">Complaints</h2>
        <ul>
          {complaints.map((c) => (
            <li key={c.id} className="mb-4 p-4 border rounded">
              <Link to={`/complaint/${c.id}`} className="font-bold text-blue-500">{c.title}</Link>
              <p>{c.description}</p>
              <p className="text-sm text-gray-500">Status: {c.status}</p>
              {user?.role === 'admin' && (
                <button
                  onClick={async () => {
                    await api.put(`/complaints/${c.id}`, { status: 'resolved' });
                    fetchComplaints();
                  }}
                  className="bg-green-500 text-white p-1 rounded mt-2"
                >
                  Resolve
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default Dashboard;