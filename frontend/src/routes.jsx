/**
 * ============================================
 * 🛣️ ROUTES CONFIGURATION
 * Mirip seperti web.php di Laravel
 * ============================================
 * 
 * File ini mendefinisikan semua routes aplikasi:
 * - Public routes (bisa diakses semua orang)
 * - Auth routes (redirect jika sudah login)
 * - Protected routes (harus login)
 * - Admin routes (hanya admin/operator)
 * 
 * URL Structure:
 * - / : Landing page (guest) atau redirect ke /chat (logged in)
 * - /chat : Halaman chat (harus login)
 * - /login : Halaman login
 * - /profile : Profil user
 * - /admin : Dashboard admin
 */

import App from './App';
import Login from './components/Login';
import AdminDashboard from './components/AdminDashboard';
import UserProfile from './components/UserProfile';
import AuthCallback from './components/AuthCallback';

// ============================================
// 📍 ROUTE DEFINITIONS
// ============================================

/**
 * PUBLIC ROUTES
 * Bisa diakses tanpa login
 */
export const publicRoutes = [
  {
    path: '/',
    element: App,
    name: 'Home',
    description: 'Halaman utama (guest mode atau redirect)'
  },
  {
    path: '/chat',
    element: App,
    name: 'Chat',
    description: 'Halaman chat utama'
  },
  {
    path: '/auth/callback',
    element: AuthCallback,
    name: 'OAuth Callback',
    description: 'Handle Google OAuth callback'
  }
];

/**
 * AUTH ROUTES
 * Untuk user yang BELUM login
 * Jika sudah login akan di-redirect
 */
export const authRoutes = [
  {
    path: '/login',
    element: Login,
    name: 'Login',
    description: 'Halaman login',
    redirectIfAuth: '/chat' // Redirect kesini jika sudah login
  },
  {
    path: '/register',
    element: Login,
    name: 'Register',
    description: 'Halaman registrasi',
    redirectIfAuth: '/chat'
  }
];

/**
 * PROTECTED ROUTES
 * Harus login untuk akses
 * Semua role bisa akses
 */
export const protectedRoutes = [
  {
    path: '/profile',
    element: UserProfile,
    name: 'Profile',
    description: 'Halaman profil user',
    roles: ['admin', 'operator', 'user']
  },
  {
    path: '/settings',
    element: UserProfile,
    name: 'Settings',
    description: 'Pengaturan akun',
    roles: ['admin', 'operator', 'user']
  }
];

/**
 * ADMIN ROUTES
 * Hanya admin dan operator yang bisa akses
 */
export const adminRoutes = [
  {
    path: '/admin',
    element: AdminDashboard,
    name: 'Admin Dashboard',
    description: 'Dashboard admin',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/users',
    element: AdminDashboard,
    name: 'User Management',
    description: 'Kelola pengguna',
    roles: ['admin']
  },
  {
    path: '/admin/stats',
    element: AdminDashboard,
    name: 'Statistics',
    description: 'Statistik sistem',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/feedback',
    element: AdminDashboard,
    name: 'Feedback',
    description: 'Lihat feedback pengguna',
    roles: ['admin', 'operator']
  }
];

// ============================================
// 📋 ALL ROUTES COMBINED
// ============================================
export const allRoutes = [
  ...publicRoutes.map(r => ({ ...r, protected: false })),
  ...protectedRoutes.map(r => ({ ...r, protected: true })),
  ...adminRoutes.map(r => ({ ...r, protected: true, isAdmin: true }))
];

// ============================================
// 🔧 ROUTE HELPERS
// ============================================

/**
 * Check if a route requires authentication
 */
export const isProtectedRoute = (path) => {
  const route = allRoutes.find(r => r.path === path);
  return route?.protected || false;
};

/**
 * Check if a route is admin-only
 */
export const isAdminRoute = (path) => {
  const route = allRoutes.find(r => r.path === path);
  return route?.isAdmin || false;
};

/**
 * Get allowed roles for a route
 */
export const getAllowedRoles = (path) => {
  const route = allRoutes.find(r => r.path === path);
  return route?.roles || [];
};

/**
 * Check if user can access a route
 */
export const canAccessRoute = (path, userRole) => {
  const route = allRoutes.find(r => r.path === path);
  
  if (!route) return false;
  if (!route.protected) return true;
  if (!userRole) return false;
  if (!route.roles || route.roles.length === 0) return true;
  
  return route.roles.includes(userRole);
};

// ============================================
// 📍 NAVIGATION MENUS
// ============================================

/**
 * Menu untuk sidebar user biasa
 */
export const userMenu = [
  { path: '/', icon: '💬', label: 'Chat' },
  { path: '/profile', icon: '👤', label: 'Profile' },
];

/**
 * Menu untuk sidebar admin
 */
export const adminMenu = [
  { path: '/', icon: '💬', label: 'Chat' },
  { path: '/admin', icon: '📊', label: 'Dashboard' },
  { path: '/admin/users', icon: '👥', label: 'Users' },
  { path: '/admin/feedback', icon: '📝', label: 'Feedback' },
  { path: '/profile', icon: '👤', label: 'Profile' },
];

export default allRoutes;
