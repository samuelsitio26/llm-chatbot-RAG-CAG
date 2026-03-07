import React, { useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { User, Lock, Eye, EyeOff, AlertCircle, Loader2, UserPlus, LogIn, ChevronDown, ChevronUp } from 'lucide-react';
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
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, register, getGoogleLoginUrl } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Refs for two-section scroll page
  const loginSectionRef = useRef(null);
  const infoSectionRef = useRef(null);

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

  // Auto-scroll to info section if URL is /information on first load
  React.useEffect(() => {
    if (location.pathname === '/information') {
      const timer = setTimeout(() => {
        infoSectionRef.current?.scrollIntoView({ behavior: 'instant' });
      }, 50);
      return () => clearTimeout(timer);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update URL based on which section is visible (IntersectionObserver)
  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            if (entry.target === infoSectionRef.current) {
              window.history.replaceState(null, '', '/information');
            } else if (entry.target === loginSectionRef.current) {
              const path = isRegisterMode ? '/register' : '/login';
              window.history.replaceState(null, '', path);
            }
          }
        });
      },
      { threshold: 0.5 }
    );
    if (loginSectionRef.current) observer.observe(loginSectionRef.current);
    if (infoSectionRef.current) observer.observe(infoSectionRef.current);
    return () => observer.disconnect();
  }, [isRegisterMode]);

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
    <div className="login-wrapper">
      {/* ====== SECTION 1: LOGIN FORM ====== */}
      <section className="login-page" ref={loginSectionRef}>
        {/* Background decorations */}
        <div className="login-bg-pattern"></div>
      
        <div className="login-container">
          {/* Left Panel - Branding */}
          <div className="login-left-panel">
            <div className="login-logo">
              <img src="/images/logo.png" alt="Toba Tourism" />
            </div>
            <h1 className="login-title">Toba Tourism</h1>
            <p className="login-subtitle">
              {isAdminLogin ? 'Admin Dashboard' : 'Sistem Rekomendasi Wisata'}
            </p>
            <p className="login-left-desc">
              Temukan destinasi wisata terbaik di kawasan Danau Toba dengan panduan AI yang cerdas dan personal
            </p>
            <div className="login-left-dots">
              <span></span><span></span><span></span>
            </div>
          </div>

          {/* Right Panel - Form */}
          <div className="login-right-panel">
            {/* Mobile compact header */}
            <div className="login-mobile-header">
              <img src="/images/logo.png" alt="Toba Tourism" />
              <div>
                <h1 className="login-title">Toba Tourism</h1>
                <p className="login-subtitle">{isAdminLogin ? 'Admin Dashboard' : 'Sistem Rekomendasi Wisata'}</p>
              </div>
            </div>

            <div className="login-form-header">
              <h2 className="login-form-title">
                {isRegisterMode ? 'Buat Akun Baru' : 'Selamat Datang'}
              </h2>
              <p className="login-form-subtitle">
                {isRegisterMode ? 'Lengkapi data berikut untuk mendaftar' : 'Masukkan kredensial Anda untuk melanjutkan'}
              </p>
            </div>

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
                  type={showConfirmPassword ? 'text' : 'password'}
                  id="confirmPassword"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Ulangi password"
                  disabled={isLoading}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  tabIndex={-1}
                >
                  {showConfirmPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
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

        {/* Scroll Down Indicator */}
        <button
          type="button"
          className="scroll-down-btn"
          onClick={() => infoSectionRef.current?.scrollIntoView({ behavior: 'smooth' })}
          aria-label="Lihat informasi aplikasi"
        >
          <span>Tentang Aplikasi</span>
          <ChevronDown size={18} className="bounce-icon" />
        </button>
      </section>

      {/* ====== SECTION 2: INFORMATION ====== */}
      <section className="info-page" ref={infoSectionRef}>
        <div className="info-content">

          {/* Header */}
          <div className="info-header">
            <img src="/images/logo.png" alt="TobaInsight" className="info-logo" />
            <h1 className="info-title">TobaInsight</h1>
            <p className="info-tagline">Sistem Rekomendasi Cerdas Pariwisata Danau Toba</p>
          </div>

          {/* Tujuan Aplikasi */}
          <div className="info-section">
            <h2 className="info-section-title">Tujuan Aplikasi</h2>
            <p className="info-description">
              TobaInsight dirancang untuk membantu wisatawan menemukan destinasi terbaik di kawasan
              Danau Toba, Sumatera Utara. Dengan teknologi AI berbasis model bahasa besar (LLM) dan
              sistem rekomendasi cerdas, aplikasi ini memberikan saran wisata yang personal dan relevan
              berdasarkan preferensi setiap pengguna.
            </p>
            <div className="info-features">
              <div className="info-feature-card">
                <span className="feature-icon">🗺️</span>
                <h3>Rekomendasi Personal</h3>
                <p>Dapatkan rekomendasi destinasi wisata yang disesuaikan dengan preferensi dan minat Anda</p>
              </div>
              <div className="info-feature-card">
                <span className="feature-icon">🤖</span>
                <h3>AI Chatbot Cerdas</h3>
                <p>Tanya jawab interaktif dengan AI tentang tempat wisata, kuliner, dan budaya Danau Toba</p>
              </div>
              <div className="info-feature-card">
                <span className="feature-icon">📍</span>
                <h3>Informasi Lengkap</h3>
                <p>Temukan detail lokasi, jam buka, harga tiket, dan tips perjalanan secara lengkap</p>
              </div>
            </div>
          </div>

          {/* Tampilan Aplikasi */}
          <div className="info-preview-section">
            <h2 className="info-section-title">Tampilan Aplikasi</h2>
            <div className="info-preview-image">
              <img src="/images/page1.png" alt="Tampilan TobaInsight" />
            </div>
          </div>

          {/* Cara Penggunaan */}
          <div className="info-section">
            <h2 className="info-section-title">Cara Penggunaan</h2>
            <div className="info-steps">
              <div className="info-step">
                <div className="step-number">1</div>
                <div className="step-content">
                  <h3>Buat Akun atau Login</h3>
                  <p>Daftarkan diri atau masuk menggunakan akun Google untuk memulai perjalanan</p>
                </div>
              </div>
              <div className="info-step">
                <div className="step-number">2</div>
                <div className="step-content">
                  <h3>Mulai Percakapan</h3>
                  <p>Ketik pertanyaan atau kebutuhan wisata Anda di kolom chat yang tersedia</p>
                </div>
              </div>
              <div className="info-step">
                <div className="step-number">3</div>
                <div className="step-content">
                  <h3>Terima Rekomendasi</h3>
                  <p>AI memberikan rekomendasi destinasi terpersonalisasi beserta informasi lengkapnya</p>
                </div>
              </div>
              <div className="info-step">
                <div className="step-number">4</div>
                <div className="step-content">
                  <h3>Jelajahi Danau Toba</h3>
                  <p>Nikmati pengalaman wisata yang lebih menyenangkan dengan panduan TobaInsight</p>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="info-footer">
            <button
              type="button"
              className="back-to-login-btn"
              onClick={() => loginSectionRef.current?.scrollIntoView({ behavior: 'smooth' })}
            >
              <ChevronUp size={18} />
              <span>Kembali ke Login</span>
            </button>
            <p className="info-copyright">© 2025 TobaInsight — Sistem Rekomendasi Pariwisata Danau Toba</p>
          </div>

        </div>
      </section>
    </div>
  );
};

export default Login;
