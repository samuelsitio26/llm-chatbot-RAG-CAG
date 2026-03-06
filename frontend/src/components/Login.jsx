import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { User, Lock, Eye, EyeOff, AlertCircle, Loader2, UserPlus, LogIn } from 'lucide-react';
import './Login.css';

// Google Icon SVG Component
const GoogleIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

const Login = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, register, getGoogleLoginUrl } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Auto-detect register mode from /register route
  const [isRegisterMode, setIsRegisterMode] = useState(location.pathname === '/register');

  // Check if coming from admin route
  const isAdminLogin = location.state?.adminLogin || location.pathname.includes('admin');

  // Sync register mode when route changes
  React.useEffect(() => {
    setIsRegisterMode(location.pathname === '/register');
  }, [location.pathname]);
  
  // Check for OAuth error in URL params
  React.useEffect(() => {
    const params = new URLSearchParams(location.search);
    const oauthError = params.get('error');
    if (oauthError) {
      setError(`Login Google gagal: ${oauthError}`);
    }
  }, [location]);

  // Handle Google Sign In - redirect to backend OAuth
  const handleGoogleSignIn = () => {
    const googleLoginUrl = getGoogleLoginUrl();
    window.location.href = googleLoginUrl;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsLoading(true);

    if (isRegisterMode) {
      // Registration validation
      if (!username.trim() || !email.trim() || !password.trim()) {
        setError('Semua field harus diisi');
        setIsLoading(false);
        return;
      }
      if (password.length < 4) {
        setError('Password minimal 4 karakter');
        setIsLoading(false);
        return;
      }
      if (password !== confirmPassword) {
        setError('Password tidak cocok');
        setIsLoading(false);
        return;
      }

      try {
        const result = await register(username, password, username, email);
        if (result.success) {
          setSuccess('Registrasi berhasil!');
          // Redirect ke halaman sebelumnya atau home
          const redirectTo = location.state?.from || '/';
          setTimeout(() => navigate(redirectTo), 1000);
        } else {
          setError(result.message);
        }
      } catch (err) {
        setError('Terjadi kesalahan saat registrasi');
      }
    } else {
      // Login validation
      if (!email.trim() || !password.trim()) {
        setError('Email dan password harus diisi');
        setIsLoading(false);
        return;
      }
      // Login
      try {
        const result = await login(email, password);
        if (result.success) {
          // Redirect ke halaman sebelumnya (jika ada) atau berdasarkan role
          const redirectTo = location.state?.from;
          
          if (redirectTo && redirectTo !== '/login' && redirectTo !== '/register') {
            // Ada halaman sebelumnya, redirect kesana
            navigate(redirectTo);
          } else if (result.role === 'admin' || result.role === 'operator') {
            // Admin/operator ke dashboard
            navigate('/admin/dashboard');
          } else {
            // User biasa ke chat
            navigate('/chat');
          }
        } else {
          setError(result.message);
        }
      } catch (err) {
        setError('Terjadi kesalahan saat login');
      }
    }
    
    setIsLoading(false);
  };

  const toggleMode = () => {
    const newMode = !isRegisterMode;
    setIsRegisterMode(newMode);
    setError('');
    setSuccess('');
    setPassword('');
    setConfirmPassword('');
    // Update URL to match mode
    navigate(newMode ? '/register' : '/login', { replace: true });
  };

  return (
    <div className="login-page">
      {/* Background decorations */}
      <div className="login-bg-pattern"></div>
      
      <div className="login-container">
        {/* Logo Section */}
        <div className="login-logo-section">
          <div className="login-logo">
            <img src="/images/logo.png" alt="Toba Tourism" />
          </div>
          <h1 className="login-title">Toba Tourism</h1>
          <p className="login-subtitle">
            {isAdminLogin ? 'Admin Dashboard' : 'Sistem Rekomendasi Wisata'}
          </p>
        </div>

        {/* Login/Register Form */}
        <form className="login-form" onSubmit={handleSubmit}>

          {error && (
            <div className="login-error">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="login-success">
              <span>✓</span>
              <span>{success}</span>
            </div>
          )}

          {isRegisterMode && (
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <div className="input-wrapper">
                <User size={20} className="input-icon" />
                <input
                  type="text"
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Masukkan username"
                  disabled={isLoading}
                />
              </div>
            </div>
          )}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <div className="input-wrapper">
              <User size={20} className="input-icon" />
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Masukkan email"
                disabled={isLoading}
                autoComplete="email"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-wrapper">
              <Lock size={20} className="input-icon" />
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Masukkan password"
                disabled={isLoading}
                autoComplete={isRegisterMode ? 'new-password' : 'current-password'}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </div>

          {isRegisterMode && (
            <div className="form-group">
              <label htmlFor="confirmPassword">Konfirmasi Password</label>
              <div className="input-wrapper">
                <Lock size={20} className="input-icon" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="confirmPassword"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Ulangi password"
                  disabled={isLoading}
                  autoComplete="new-password"
                />
              </div>
            </div>
          )}

          <button type="submit" className="login-button" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 size={20} className="spin" />
                <span>Memproses...</span>
              </>
            ) : isRegisterMode ? (
              <>
                <UserPlus size={20} />
                <span>Daftar</span>
              </>
            ) : (
              <>
                <LogIn size={20} />
                <span>Login</span>
              </>
            )}
          </button>

          {/* Toggle Login/Register */}
          <div className="auth-toggle">
            <span>{isRegisterMode ? 'Sudah punya akun?' : 'Belum punya akun?'}</span>
            <button type="button" onClick={toggleMode} className="toggle-btn">
              {isRegisterMode ? 'Login di sini' : 'Daftar di sini'}
            </button>
          </div>

          {/* Divider */}
          <div className="auth-divider">
            <span>atau</span>
          </div>

          {/* Google Sign In Button */}
          <button
            type="button"
            className="google-signin-btn"
            onClick={handleGoogleSignIn}
            disabled={isLoading}
          >
            <GoogleIcon />
            <span>Lanjutkan dengan Google</span>
          </button>



        </form>
      </div>
    </div>
  );
};

export default Login;
