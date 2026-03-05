/**
 * ============================================
 * 🚀 MAIN ENTRY POINT
 * Tourism Chatbot Toba
 * ============================================
 * 
 * Routing di React mirip seperti web.php di Laravel
 * 
 * URL Structure:
 * - /         → Home (redirect ke /chat jika login)
 * - /chat     → Halaman chat utama
 * - /login    → Login (redirect ke /chat jika sudah login)
 * - /profile  → Profil user (harus login)
 * - /admin    → Dashboard admin (harus admin/operator)
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import GuestRoute from './components/GuestRoute';
import './index.css';

/**
 * Root redirect: belum login → /login, sudah login → /chat
 */
const HomeRedirect = () => {
  const { isAuthenticated, isLoading, authChecked } = useAuth();
  if (isLoading || !authChecked) return null;
  return <Navigate to={isAuthenticated ? '/chat' : '/login'} replace />;
};

// Import Routes Configuration (seperti web.php di Laravel)
import { publicRoutes, authRoutes, protectedRoutes, adminRoutes } from './routes';

// ============================================
// 🛣️ ROUTE RENDERERS
// ============================================

/** Render public routes (bisa diakses semua) */
const renderPublicRoutes = () => {
  return publicRoutes.map((route) => (
    <Route 
      key={route.path} 
      path={route.path} 
      element={<route.element />} 
    />
  ));
};

/** Render auth routes (untuk guest, redirect jika sudah login) */
const renderAuthRoutes = () => {
  return authRoutes.map((route) => (
    <Route
      key={route.path}
      path={route.path}
      element={
        <GuestRoute redirectTo={route.redirectIfAuth || '/chat'}>
          <route.element />
        </GuestRoute>
      }
    />
  ));
};

/** Render protected routes (perlu login) */
const renderProtectedRoutes = () => {
  return protectedRoutes.map((route) => (
    <Route
      key={route.path}
      path={route.path}
      element={
        <ProtectedRoute allowedRoles={route.roles}>
          <route.element />
        </ProtectedRoute>
      }
    />
  ));
};

/** Render admin routes (perlu login + role admin/operator) */
const renderAdminRoutes = () => {
  return adminRoutes.map((route) => (
    <Route
      key={route.path}
      path={route.path}
      element={
        <ProtectedRoute allowedRoles={route.roles}>
          <route.element />
        </ProtectedRoute>
      }
    />
  ));
};

// ============================================
// 🎯 APP MOUNT
// ============================================

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* ROOT REDIRECT - Login dulu baru bisa akses */}
          <Route path="/" element={<HomeRedirect />} />

          {/* PUBLIC ROUTES - Bisa diakses semua (hanya OAuth callback) */}
          {renderPublicRoutes()}

          {/* AUTH ROUTES - Untuk guest, redirect jika sudah login */}
          {renderAuthRoutes()}

          {/* PROTECTED ROUTES - Harus login */}
          {renderProtectedRoutes()}

          {/* ADMIN ROUTES - Hanya admin/operator */}
          {renderAdminRoutes()}

          {/* /admin redirect ke /admin/dashboard */}
          <Route 
            path="/admin" 
            element={<Navigate to="/admin/dashboard" replace />} 
          />

          {/* CATCH-ALL - Redirect ke home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
