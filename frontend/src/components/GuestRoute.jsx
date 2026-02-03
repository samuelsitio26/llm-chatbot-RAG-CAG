/**
 * ============================================
 * 🚪 GUEST ROUTE COMPONENT
 * Redirect ke halaman lain jika sudah login
 * ============================================
 * 
 * Kebalikan dari ProtectedRoute:
 * - Jika SUDAH login → redirect ke redirectTo
 * - Jika BELUM login → render children
 * 
 * Contoh: Halaman login tidak perlu diakses jika sudah login
 */

import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const GuestRoute = ({ children, redirectTo = '/chat' }) => {
  const { user, isLoading, isAuthenticated, authChecked } = useAuth();
  const location = useLocation();

  // Show loading state while checking authentication
  if (isLoading || !authChecked) {
    return (
      <div className="loading-screen" style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a1929 0%, #1a3a4a 50%, #0a1929 100%)',
        color: 'white'
      }}>
        <div className="loading-spinner" style={{
          width: '50px',
          height: '50px',
          border: '4px solid rgba(255,255,255,0.1)',
          borderTop: '4px solid #dc2626',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite'
        }}></div>
        <p style={{ marginTop: '1rem', color: '#fbbf24' }}>Memuat...</p>
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // Jika sudah login, redirect ke halaman yang ditentukan
  if (isAuthenticated) {
    // Cek apakah ada halaman yang diminta sebelumnya
    const from = location.state?.from;
    const destination = from || redirectTo;
    
    console.log(`✅ User authenticated, redirecting to: ${destination}`);
    return <Navigate to={destination} replace />;
  }

  // Belum login, tampilkan halaman (misal: login page)
  return children;
};

export default GuestRoute;
