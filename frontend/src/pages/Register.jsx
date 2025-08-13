import React from 'react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import api from '../api';

function Register() {
  const { register, handleSubmit } = useForm();
  const navigate = useNavigate();

  const onSubmit = async (data) => {
    try {
      await api.post('/users/register', data);
      alert('Registered! Please login.');
      navigate('/login');
    } catch (error) {
      alert('Registration failed: ' + error.response?.data?.detail);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <form onSubmit={handleSubmit(onSubmit)} className="bg-white p-8 rounded shadow-md w-96">
        <h1 className="text-2xl font-bold mb-6">Register</h1>
        <input {...register('email')} type="email" placeholder="Email" className="w-full p-2 mb-4 border rounded" required />
        <input {...register('password')} type="password" placeholder="Password" className="w-full p-2 mb-4 border rounded" required />
        {/* Add role if your backend supports: <select {...register('role')}><option>student</option><option>admin</option></select> */}
        <button type="submit" className="w-full bg-green-500 text-white p-2 rounded">Register</button>
      </form>
    </div>
  );
}

export default Register;