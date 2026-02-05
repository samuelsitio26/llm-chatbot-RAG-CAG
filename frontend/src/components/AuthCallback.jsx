import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';

/**
 * AuthCallback Component
 * Handles OAuth callback from Google login
 * URL: /auth/callback?token=xxx
 */
const AuthCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleOAuthCallback } = useAuth();
  const [status, setStatus] = useState('processing'); // processing, success, error
  const [message, setMessage] = useState('Memproses login...');

  useEffect(() => {
    const processCallback = async () => {
      const token = searchParams.get('token');
      const error = searchParams.get('error');

      if (error) {
        setStatus('error');
        setMessage(`Login gagal: ${error}`);
        setTimeout(() => navigate('/login'), 3000);
        return;
      }

      if (!token) {
        setStatus('error');
        setMessage('Token tidak ditemukan');
        setTimeout(() => navigate('/login'), 3000);
        return;
      }

      try {
        // Process the OAuth token
        const result = await handleOAuthCallback(token);
        
        if (result.success) {
          setStatus('success');
          setMessage('Login berhasil! Mengalihkan...');
          setTimeout(() => {
            // Redirect based on role
            if (result.role === 'admin' || result.role === 'operator') {
              navigate('/admin');
            } else {
              navigate('/chat');
            }
          }, 1500);
        } else {
          setStatus('error');
          setMessage(result.message || 'Login gagal');
          setTimeout(() => navigate('/login'), 3000);
        }
      } catch (err) {
        console.error('OAuth callback error:', err);
        setStatus('error');
        setMessage('Terjadi kesalahan saat memproses login');
        setTimeout(() => navigate('/login'), 3000);
      }
    };

    processCallback();
  }, [searchParams, navigate, handleOAuthCallback]);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0a1929 0%, #1a237e 100%)',
      color: 'white',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{
        textAlign: 'center',
        padding: '40px',
        background: 'rgba(255,255,255,0.1)',
        borderRadius: '16px',
        backdropFilter: 'blur(10px)'
      }}>
        {status === 'processing' && (
          <>
            <Loader2 size={48} className="spin" style={{ marginBottom: '16px', animation: 'spin 1s linear infinite' }} />
            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
          </>
        )}
        {status === 'success' && (
          <CheckCircle size={48} style={{ marginBottom: '16px', color: '#4caf50' }} />
        )}
        {status === 'error' && (
          <XCircle size={48} style={{ marginBottom: '16px', color: '#f44336' }} />
        )}
        
        <h2 style={{ margin: '0 0 8px 0', fontSize: '24px' }}>
          {status === 'processing' && 'Memproses...'}
          {status === 'success' && 'Berhasil!'}
          {status === 'error' && 'Gagal'}
        </h2>
        
        <p style={{ margin: 0, opacity: 0.8 }}>{message}</p>
      </div>
    </div>
  );
};

export default AuthCallback;
