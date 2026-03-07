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
 * - /register : Halaman registrasi
 * - /profile : Profil user
 * - /admin/dashboard : Dashboard admin
 * - /admin/usermanagement : Kelola pengguna
 * - /admin/lokasiwisata : Lokasi wisata
 * - /admin/faqmanagement : FAQ Management
 * - /admin/analytics : Analytics
 * - /admin/systemstatus : System Status
 * - /admin/settings : Settings
 * - /admin/chat : Chat (admin)
 * - /admin/profile : Profile (admin)
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
    path: '/auth/callback',
    element: AuthCallback,
    name: 'OAuth Callback',
    description: 'Handle Google OAuth callback'
  },
  {
    path: '/information',
    element: Login,
    name: 'Information',
    description: 'Informasi tentang aplikasi TobaInsight'
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
    path: '/chat',
    element: App,
    name: 'Chat',
    description: 'Halaman chat utama',
    roles: ['admin', 'operator', 'user']
  },
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
    path: '/admin/dashboard',
    element: AdminDashboard,
    name: 'Admin Dashboard',
    description: 'Dashboard admin',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/usermanagement',
    element: AdminDashboard,
    name: 'User Management',
    description: 'Kelola pengguna',
    roles: ['admin']
  },
  {
    path: '/admin/lokasiwisata',
    element: AdminDashboard,
    name: 'Lokasi Wisata',
    description: 'Kelola lokasi wisata',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/faqmanagement',
    element: AdminDashboard,
    name: 'FAQ Management',
    description: 'Kelola FAQ',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/analytics',
    element: AdminDashboard,
    name: 'Analytics',
    description: 'Statistik dan analitik',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/systemstatus',
    element: AdminDashboard,
    name: 'System Status',
    description: 'Status sistem',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/settings',
    element: AdminDashboard,
    name: 'Settings',
    description: 'Pengaturan sistem',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/cachecontrol',
    element: AdminDashboard,
    name: 'Cache Control',
    description: 'Kontrol KV cache chatbot',
    roles: ['admin']
  },
  {
    path: '/admin/chat',
    element: App,
    name: 'Chat',
    description: 'Halaman chat (admin)',
    roles: ['admin', 'operator']
  },
  {
    path: '/admin/profile',
    element: UserProfile,
    name: 'Profile',
    description: 'Profil admin',
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
  { path: '/admin/dashboard', icon: '📊', label: 'Dashboard' },
  { path: '/admin/usermanagement', icon: '👥', label: 'User Management' },
  { path: '/admin/lokasiwisata', icon: '📍', label: 'Lokasi Wisata' },
  { path: '/admin/faqmanagement', icon: '💬', label: 'FAQ Management' },
  { path: '/admin/analytics', icon: '📈', label: 'Analytics' },
  { path: '/admin/systemstatus', icon: '🖥️', label: 'System Status' },
  { path: '/admin/cachecontrol', icon: '🗄️', label: 'Cache Control' },
  { path: '/admin/settings', icon: '⚙️', label: 'Settings' },
  { path: '/admin/chat', icon: '💬', label: 'Chat' },
  { path: '/admin/profile', icon: '👤', label: 'Profile' },
];

export default allRoutes;
