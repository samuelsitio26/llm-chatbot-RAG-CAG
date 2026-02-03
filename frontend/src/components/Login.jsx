import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { User, Lock, Eye, EyeOff, AlertCircle, Loader2, UserPlus, LogIn, ArrowLeft } from 'lucide-react';
import './Login.css';

const Login = () => {
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Check if coming from admin route
  const isAdminLogin = location.state?.adminLogin || location.pathname.includes('admin');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsLoading(true);

    if (!username.trim() || !password.trim()) {
      setError('Username dan password harus diisi');
      setIsLoading(false);
      return;
    }

    if (isRegisterMode) {
      // Registration
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
        const result = await register(username, password, displayName);
        if (result.success) {
          setSuccess('Registrasi berhasil!');
          setTimeout(() => navigate('/'), 1000);
        } else {
          setError(result.message);
        }
      } catch (err) {
        setError('Terjadi kesalahan saat registrasi');
      }
    } else {
      // Login
      try {
        const result = await login(username, password);
        if (result.success) {
          // Redirect based on role
          if (result.role === 'admin' || result.role === 'operator') {
            navigate('/admin');
          } else {
            navigate('/');
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
    setIsRegisterMode(!isRegisterMode);
    setError('');
    setSuccess('');
    setPassword('');
    setConfirmPassword('');
  };

  return (
    <div className="login-page">
      {/* Background decorations */}
      <div className="login-bg-pattern"></div>
      
      <div className="login-container">
        {/* Back Button - Top Left */}
        <Link to="/" className="back-btn-box">
          <ArrowLeft size={20} />
        </Link>

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
              <label htmlFor="displayName">Nama Tampilan</label>
              <div className="input-wrapper">
                <User size={20} className="input-icon" />
                <input
                  type="text"
                  id="displayName"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Nama yang akan ditampilkan"
                  disabled={isLoading}
                />
              </div>
            </div>
          )}

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
                autoComplete="username"
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


          {/* Demo credentials hint - only show on login mode */}
          {!isRegisterMode && (
            <div className="demo-hint">
              <p><strong>Demo Credentials:</strong></p>
              <p>Admin: admin / admin123</p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default Login;
