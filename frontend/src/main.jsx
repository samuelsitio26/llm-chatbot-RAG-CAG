import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import App from './App.jsx';
import Login from './components/Login';
import AdminDashboard from './components/AdminDashboard';
import UserProfile from './components/UserProfile';
import ProtectedRoute from './components/ProtectedRoute';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<App />} />
          <Route path="/login" element={<Login />} />
          
          {/* User Profile - Semua user yang login */}
          <Route 
            path="/profile" 
            element={
              <ProtectedRoute allowedRoles={['admin', 'operator', 'user']}>
                <UserProfile />
              </ProtectedRoute>
            } 
          />
          
          {/* Protected Admin Routes */}
          <Route 
            path="/admin" 
            element={
              <ProtectedRoute allowedRoles={['admin', 'operator']}>
                <AdminDashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/admin/*" 
            element={
              <ProtectedRoute allowedRoles={['admin', 'operator']}>
                <AdminDashboard />
              </ProtectedRoute>
            } 
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
