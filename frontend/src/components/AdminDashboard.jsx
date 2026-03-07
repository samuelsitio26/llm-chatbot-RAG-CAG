import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import {
  LayoutDashboard,
  Users,
  MapPin,
  MessageSquare,
  Settings,
  LogOut,
  Menu,
  X,
  Bell,
  Search,
  TrendingUp,
  Database,
  Server,
  Activity,
  Clock,
  ChevronRight,
  ChevronDown,
  FileText,
  BarChart3,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Home,
  Volume2,
  UserCircle,
  User,
  Trash2,
  Edit,
  Plus,
  Save,
  XCircle,
  ShieldAlert,
  Eye,
  Play,
} from 'lucide-react';
import './AdminDashboard.css';

const API_BASE_URL = '/api';

// Helper function to check if avatar is an image URL
const isImageAvatar = (avatar) => {
  return avatar && (
    avatar.startsWith('/api/avatars/') || 
    avatar.startsWith('data:image') || 
    avatar.startsWith('http://') ||
    avatar.startsWith('https://')
  );
};

// Avatar component that handles both emoji and image URLs
const Avatar = ({ src, size = 'small', className = '' }) => {
  const [imageError, setImageError] = React.useState(false);
  
  // Reset error state when src changes
  React.useEffect(() => {
    setImageError(false);
  }, [src]);
  
  if (isImageAvatar(src) && !imageError) {
    return (
      <img 
        src={src} 
        alt="Avatar" 
        className={`avatar-img ${className}`}
        style={{
          width: size === 'small' ? '32px' : size === 'medium' ? '40px' : '48px',
          height: size === 'small' ? '32px' : size === 'medium' ? '40px' : '48px',
          borderRadius: '50%',
          objectFit: 'cover'
        }}
        crossOrigin="anonymous"
        referrerPolicy="no-referrer"
        onError={() => setImageError(true)}
      />
    );
  }
  return (
    <span className={`avatar-emoji ${className}`} style={{
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: size === 'small' ? '32px' : size === 'medium' ? '40px' : '48px',
      height: size === 'small' ? '32px' : size === 'medium' ? '40px' : '48px',
      fontSize: size === 'small' ? '1rem' : size === 'medium' ? '1.25rem' : '1.5rem'
    }}>
      {src || '👤'}
    </span>
  );
};

const AdminDashboard = () => {
  const { user, token, logout, getAllUsers } = useAuth();
  const getAuthHeaders = () => token ? { Authorization: `Bearer ${token}` } : {};
  const navigate = useNavigate();
  const location = useLocation();

  // Map URL paths to menu IDs
  const pathToMenu = {
    '/admin/dashboard': 'dashboard',
    '/admin/usermanagement': 'users',
    '/admin/lokasiwisata': 'locations',
    '/admin/faqmanagement': 'faqs',
    '/admin/cachecontrol': 'cache',
    '/admin/analytics': 'analytics',
    '/admin/systemstatus': 'dashboard',
    '/admin/settings': 'settings',
  };

  // Map menu IDs to URL paths
  const menuToPath = {
    'dashboard': '/admin/dashboard',
    'users': '/admin/usermanagement',
    'locations': '/admin/lokasiwisata',
    'faqs': '/admin/faqmanagement',
    'cache': '/admin/cachecontrol',
    'analytics': '/admin/analytics',
    'settings': '/admin/settings',
  };

  const getActiveMenuFromPath = () => pathToMenu[location.pathname] || 'dashboard';

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState(getActiveMenuFromPath());
  const [systemStatus, setSystemStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locations, setLocations] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [adminStats, setAdminStats] = useState(null);
  const [isMusicPlaying, setIsMusicPlaying] = useState(false);
  const [musicHasPlayed, setMusicHasPlayed] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const audioRef = useRef(null);
  const userMenuRef = useRef(null);

  // Sync activeMenu when URL changes
  useEffect(() => {
    const menuFromPath = getActiveMenuFromPath();
    if (menuFromPath !== activeMenu) {
      setActiveMenu(menuFromPath);
    }
  }, [location.pathname]);

  // Close user menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target)) {
        setShowUserMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Play welcome music once every time user enters dashboard (after login)
  useEffect(() => {
    // Only play if music hasn't played yet in this dashboard session
    if (!musicHasPlayed && audioRef.current) {
      // Small delay to ensure component is mounted
      const playMusic = setTimeout(() => {
        audioRef.current.volume = 0.5; // Set volume to 50%
        audioRef.current.play()
          .then(() => {
            setIsMusicPlaying(true);
            setMusicHasPlayed(true); // Mark as played for this dashboard visit
            console.log('🎵 Welcome music playing...');
          })
          .catch((err) => {
            console.log('Audio autoplay blocked:', err);
            // If autoplay is blocked, user can click the music button
          });
      }, 500);
      
      return () => clearTimeout(playMusic);
    }
  }, [musicHasPlayed]);

  // Handle audio end
  const handleAudioEnd = () => {
    setIsMusicPlaying(false);
    console.log('🎵 Music finished');
  };

  // Toggle music play/pause - replay from beginning when clicked
  const toggleMusic = () => {
    if (audioRef.current) {
      if (isMusicPlaying) {
        audioRef.current.pause();
        setIsMusicPlaying(false);
      } else {
        // Reset to beginning and play
        audioRef.current.currentTime = 0;
        audioRef.current.play()
          .then(() => setIsMusicPlaying(true))
          .catch(err => console.log('Play error:', err));
      }
    }
  };

  useEffect(() => {
    fetchSystemStatus();
    fetchStats();
    fetchAdminStats();
    fetchLocations();
    fetchFAQs();
    const interval = setInterval(() => {
      fetchSystemStatus();
      fetchStats();
      fetchAdminStats();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchSystemStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/status`);
      setSystemStatus(response.data);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAdminStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/admin/stats`, {
        headers: getAuthHeaders(),
      });
      setAdminStats(response.data);
    } catch (error) {
      console.error('Error fetching admin stats:', error);
    }
  };

  const fetchLocations = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/locations`);
      if (response.data.locations) {
        setLocations(response.data.locations);
      }
    } catch (error) {
      console.error('Error fetching locations:', error);
    }
  };

  const fetchFAQs = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/faqs`);
      if (response.data.faqs) {
        setFaqs(response.data.faqs);
      }
    } catch (error) {
      console.error('Error fetching FAQs:', error);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/admin/dashboard' },
    { id: 'users', label: 'User Management', icon: Users, path: '/admin/usermanagement' },
    { id: 'locations', label: 'Lokasi Wisata', icon: MapPin, path: '/admin/lokasiwisata' },
    { id: 'faqs', label: 'FAQ Management', icon: MessageSquare, path: '/admin/faqmanagement' },
    { id: 'cache', label: 'Cache Control', icon: Database, path: '/admin/cachecontrol' },
    { id: 'analytics', label: 'Analytics', icon: BarChart3, path: '/admin/analytics' },
    { id: 'settings', label: 'Settings', icon: Settings, path: '/admin/settings' },
  ];

  const renderContent = () => {
    switch (activeMenu) {
      case 'dashboard':
        return <DashboardOverview
          stats={stats}
          adminStats={adminStats}
          systemStatus={systemStatus}
          locations={locations}
          faqs={faqs}
          loading={loading}
          onNavigate={(menuId) => navigate(menuToPath[menuId] || '/admin/dashboard')}
        />;
      case 'users':
        return <UsersManagement getAllUsers={getAllUsers} />;
      case 'locations':
        return <LocationsManagement locations={locations} />;
      case 'faqs':
        return <FAQManagement getAuthHeaders={getAuthHeaders} />;
      case 'cache':
        return <CacheControl getAuthHeaders={getAuthHeaders} stats={stats} onRefresh={fetchStats} />;
      case 'analytics':
        return <AnalyticsView getAuthHeaders={getAuthHeaders} />;
      case 'settings':
        return <SettingsView user={user} />;
      default:
        return <DashboardOverview stats={stats} systemStatus={systemStatus} locations={locations} loading={loading} />;
    }
  };

  return (
    <div className="admin-layout">
      {/* Background Music */}
      <audio 
        ref={audioRef} 
        src="/song/tobadream.mp3" 
        onEnded={handleAudioEnd}
        preload="auto"
      />

      {/* Sidebar */}
      <aside className={`admin-sidebar ${sidebarOpen ? 'open' : 'collapsed'} ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-icon">🏔️</div>
            {sidebarOpen && <span className="logo-text">Toba Admin</span>}
          </div>
          <button className="sidebar-toggle desktop-only" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <Menu size={20} />
          </button>
          <button className="sidebar-toggle mobile-only" onClick={() => setMobileMenuOpen(false)}>
            <X size={20} />
          </button>
        </div>

        <nav className="sidebar-nav">
          {menuItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeMenu === item.id ? 'active' : ''}`}
              onClick={() => {
                navigate(item.path);
                setMobileMenuOpen(false);
              }}
            >
              <item.icon size={20} />
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <Link to="/admin/chat" className="nav-item home-link">
            <Home size={20} />
            {sidebarOpen && <span>Chat</span>}
          </Link>
          <button className="nav-item logout-btn" onClick={handleLogout}>
            <LogOut size={20} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div className="mobile-overlay" onClick={() => setMobileMenuOpen(false)} />
      )}

      {/* Main Content */}
      <main className="admin-main">
        {/* Top Bar */}
        <header className="admin-topbar">
          <div className="topbar-left">
            <button className="mobile-menu-btn" onClick={() => setMobileMenuOpen(true)}>
              <Menu size={24} />
            </button>
            <h1 className="page-title">{menuItems.find(m => m.id === activeMenu)?.label || 'Dashboard'}</h1>
          </div>
          <div className="topbar-right">
            <div className="search-box">
              <Search size={18} />
              <input type="text" placeholder="Cari..." />
            </div>
            {/* Music Toggle Button - Subtle when not playing */}
            <button 
              className={`topbar-btn music-btn ${isMusicPlaying ? 'playing' : 'hidden-music'}`}
              onClick={toggleMusic}
              title={isMusicPlaying ? 'Pause Music' : 'Play Music'}
            >
              {isMusicPlaying ? <Volume2 size={20} /> : <ChevronDown size={16} />}
              {isMusicPlaying && <span className="music-indicator"></span>}
            </button>
            <button className="topbar-btn">
              <Bell size={20} />
              <span className="notification-badge">3</span>
            </button>
            
            {/* User Menu Dropdown */}
            <div className="user-menu-container" ref={userMenuRef}>
              <button 
                className="user-menu-trigger"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                <div className="user-avatar">
                  <Avatar src={user?.avatar} size="small" />
                </div>
                <div className="user-info">
                  <span className="user-name">{user?.name || 'Admin'}</span>
                  <span className="user-role">{user?.role || 'Administrator'}</span>
                </div>
                <ChevronDown 
                  size={16} 
                  className={`menu-chevron ${showUserMenu ? 'rotated' : ''}`}
                />
              </button>
              
              {showUserMenu && (
                <div className="user-dropdown">
                  <Link 
                    to="/admin/profile" 
                    className="dropdown-item"
                    onClick={() => setShowUserMenu(false)}
                  >
                    <User size={18} />
                    <span>Profile</span>
                  </Link>
                  <button 
                    className="dropdown-item logout"
                    onClick={() => {
                      setShowUserMenu(false);
                      handleLogout();
                    }}
                  >
                    <LogOut size={18} />
                    <span>Logout</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="admin-content">
          {renderContent()}
        </div>
      </main>
    </div>
  );
};

// Dashboard Overview Component
const DashboardOverview = ({ stats, adminStats, systemStatus, locations, faqs, loading, onNavigate }) => {
  const kvCache     = stats?.kv_cache || {};
  const sysStats    = adminStats?.stats || {};
  const fbStats     = adminStats?.feedback || {};

  const statCards = [
    {
      title: 'Total Percakapan',
      value: sysStats.totalChats ?? 0,
      sub: `${sysStats.chatsToday ?? 0} hari ini`,
      icon: MessageSquare,
      color: 'blue',
      menu: 'analytics',
    },
    {
      title: 'Cache Entries',
      value: kvCache.size ?? 0,
      sub: `${kvCache.staging_items ?? 0} staging`,
      icon: Database,
      color: 'green',
      menu: 'cache',
    },
    {
      title: 'Total Pengguna',
      value: sysStats.totalUsers ?? 0,
      sub: `${sysStats.activeSessions ?? 0} sesi aktif`,
      icon: Users,
      color: 'purple',
      menu: 'users',
    },
    {
      title: 'Lokasi Wisata',
      value: locations?.length ?? 0,
      sub: 'terdaftar',
      icon: MapPin,
      color: 'orange',
      menu: 'locations',
    },
    {
      title: 'Total FAQ',
      value: faqs?.length ?? 0,
      sub: 'entri terdaftar',
      icon: FileText,
      color: 'teal',
      menu: 'faqs',
    },
    {
      title: 'Rating Rata-rata',
      value: fbStats.averageRating ? fbStats.averageRating.toFixed(1) : '–',
      sub: `dari ${fbStats.totalFeedback ?? 0} feedback`,
      icon: TrendingUp,
      color: 'red',
      menu: 'analytics',
    },
  ];

  const isHealthy = systemStatus?.status === 'healthy' || systemStatus?.model_loaded;

  return (
    <div className="dashboard-overview">
      {/* Stat Cards */}
      <div className="stat-cards stat-cards-6">
        {statCards.map((stat, index) => (
          <div
            key={index}
            className={`stat-card ${stat.color} stat-card-clickable`}
            onClick={() => onNavigate(stat.menu)}
            title={`Buka ${stat.title}`}
          >
            <div className="stat-icon">
              <stat.icon size={24} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{loading ? '...' : stat.value}</span>
              <span className="stat-label">{stat.title}</span>
              {stat.sub && <span className="stat-sub">{loading ? '' : stat.sub}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* System Health + Summary Cards */}
      <div className="dashboard-grid">
        <div className="dashboard-card system-health">
          <div className="card-header">
            <h3>System Health</h3>
            <span className={`status-badge ${isHealthy ? 'healthy' : 'warning'}`}>
              {isHealthy ? (
                <><CheckCircle size={14} /> Healthy</>
              ) : (
                <><AlertTriangle size={14} /> Warning</>
              )}
            </span>
          </div>
          <div className="health-items">
            <div className="health-item">
              <Server size={18} />
              <span>Model</span>
              <span className={`health-status ${systemStatus?.model_loaded ? 'active' : 'inactive'}`}>
                {systemStatus?.model_loaded ? 'Loaded ✓' : 'Not Loaded'}
              </span>
            </div>
            <div className="health-item">
              <Database size={18} />
              <span>KV Cache</span>
              <span className="health-status active" style={{ cursor: 'pointer' }} onClick={() => onNavigate('cache')}>
                {kvCache.size ?? 0} confirmed · {kvCache.staging_items ?? 0} staging
              </span>
            </div>
            <div className="health-item">
              <Users size={18} />
              <span>Sesi Aktif</span>
              <span className="health-status active" onClick={() => onNavigate('users')} style={{ cursor: 'pointer' }}>
                {sysStats.activeSessions ?? 0} sesi
              </span>
            </div>
            <div className="health-item">
              <Activity size={18} />
              <span>Uptime</span>
              <span className="health-status active">
                {systemStatus?.uptime || 'N/A'}
              </span>
            </div>
            <div className="health-item">
              <MessageSquare size={18} />
              <span>FAQ</span>
              <span className="health-status active" onClick={() => onNavigate('faqs')} style={{ cursor: 'pointer' }}>
                {faqs?.length ?? 0} entri
              </span>
            </div>
            <div className="health-item">
              <MapPin size={18} />
              <span>Lokasi</span>
              <span className="health-status active" onClick={() => onNavigate('locations')} style={{ cursor: 'pointer' }}>
                {locations?.length ?? 0} terdaftar
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card recent-activity">
          <div className="card-header">
            <h3>Ringkasan Data</h3>
          </div>
          <div className="activity-list">
            <div className="activity-item" onClick={() => onNavigate('analytics')} style={{ cursor: 'pointer' }}>
              <div className="activity-icon blue">
                <MessageSquare size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">{sysStats.chatsToday ?? 0} percakapan hari ini</span>
                <span className="activity-time">Total: {sysStats.totalChats ?? 0} semua waktu</span>
              </div>
              <ChevronRight size={14} style={{ color: '#64748b' }} />
            </div>
            <div className="activity-item" onClick={() => onNavigate('users')} style={{ cursor: 'pointer' }}>
              <div className="activity-icon purple">
                <Users size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">{sysStats.recentRegistrations ?? 0} pengguna baru (7 hari)</span>
                <span className="activity-time">Total: {sysStats.totalUsers ?? 0} pengguna aktif</span>
              </div>
              <ChevronRight size={14} style={{ color: '#64748b' }} />
            </div>
            <div className="activity-item" onClick={() => onNavigate('cache')} style={{ cursor: 'pointer' }}>
              <div className="activity-icon green">
                <Database size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">{kvCache.size ?? 0} cache confirmed</span>
                <span className="activity-time">{kvCache.staging_items ?? 0} menunggu review di staging</span>
              </div>
              <ChevronRight size={14} style={{ color: '#64748b' }} />
            </div>
            <div className="activity-item" onClick={() => onNavigate('analytics')} style={{ cursor: 'pointer' }}>
              <div className="activity-icon" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>
                <TrendingUp size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">Rating rata-rata: {fbStats.averageRating?.toFixed(1) ?? '–'}</span>
                <span className="activity-time">{fbStats.totalFeedback ?? 0} total feedback pengguna</span>
              </div>
              <ChevronRight size={14} style={{ color: '#64748b' }} />
            </div>
            <div className="activity-item" onClick={() => onNavigate('faqs')} style={{ cursor: 'pointer' }}>
              <div className="activity-icon" style={{ background: 'rgba(20,184,166,0.15)', color: '#2dd4bf' }}>
                <FileText size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">{faqs?.length ?? 0} FAQ terdaftar</span>
                <span className="activity-time">Klik untuk kelola FAQ</span>
              </div>
              <ChevronRight size={14} style={{ color: '#64748b' }} />
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="quick-actions">
        <h3>Quick Actions</h3>
        <div className="action-buttons">
          <button className="action-btn" onClick={() => onNavigate('analytics')}>
            <BarChart3 size={20} />
            <span>Lihat Analytics</span>
          </button>
          <button className="action-btn" onClick={() => onNavigate('cache')}>
            <Database size={20} />
            <span>Cache Control</span>
          </button>
          <button className="action-btn" onClick={() => onNavigate('users')}>
            <Users size={20} />
            <span>Kelola User</span>
          </button>
          <button className="action-btn" onClick={() => onNavigate('faqs')}>
            <MessageSquare size={20} />
            <span>Kelola FAQ</span>
          </button>
          <button className="action-btn" onClick={() => onNavigate('locations')}>
            <MapPin size={20} />
            <span>Lokasi Wisata</span>
          </button>
        </div>
      </div>
    </div>
  );
};

// Locations Management Component
const LocationsManagement = ({ locations }) => {
  return (
    <div className="management-view">
      <div className="view-header">
        <h2>Lokasi Wisata</h2>
        <button className="add-btn">
          <MapPin size={18} />
          <span>Tambah Lokasi</span>
        </button>
      </div>
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nama</th>
              <th>Kategori</th>
              <th>Lokasi</th>
              <th>Rating</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {locations.length > 0 ? (
              locations.slice(0, 10).map((loc, index) => (
                <tr key={index}>
                  <td>{loc.name}</td>
                  <td><span className="category-badge">{loc.category || 'Wisata'}</span></td>
                  <td>{loc.lat?.toFixed(4)}, {loc.lng?.toFixed(4)}</td>
                  <td>⭐ {loc.rating || 4.5}</td>
                  <td>
                    <div className="action-btns">
                      <button className="btn-edit">Edit</button>
                      <button className="btn-delete">Delete</button>
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="5" className="empty-state">Tidak ada data lokasi</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// FAQ Management Component — full CRUD (question + answer only)
const FAQManagement = ({ getAuthHeaders }) => {
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [formMode, setFormMode] = useState(null); // null | 'add' | 'edit'
  const [editIndex, setEditIndex] = useState(null);
  const [formData, setFormData] = useState({ question: '', answer: '' });
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null); // index to delete
  const [toast, setToast] = useState(null); // { type: 'success'|'error', msg }

  const showToast = (type, msg) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchFAQs = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/faqs`);
      setFaqs(res.data.faqs || []);
    } catch (e) {
      showToast('error', 'Gagal memuat FAQ');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchFAQs(); }, []);

  const openAdd = () => {
    setFormData({ question: '', answer: '' });
    setEditIndex(null);
    setFormMode('add');
  };

  const openEdit = (idx) => {
    setFormData({ question: faqs[idx].question, answer: faqs[idx].answer });
    setEditIndex(idx);
    setFormMode('edit');
  };

  const cancelForm = () => { setFormMode(null); setEditIndex(null); };

  const handleSave = async () => {
    if (!formData.question.trim() || !formData.answer.trim()) {
      showToast('error', 'Pertanyaan dan jawaban wajib diisi');
      return;
    }
    setSaving(true);
    try {
      if (formMode === 'add') {
        await axios.post(`${API_BASE_URL}/faqs`, formData, { headers: getAuthHeaders() });
        showToast('success', 'FAQ berhasil ditambahkan');
      } else {
        await axios.put(`${API_BASE_URL}/faqs/${editIndex}`, formData, { headers: getAuthHeaders() });
        showToast('success', 'FAQ berhasil diperbarui');
      }
      setFormMode(null);
      setEditIndex(null);
      fetchFAQs();
    } catch (e) {
      showToast('error', e.response?.data?.detail || 'Gagal menyimpan FAQ');
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = (idx) => setDeleteConfirm(idx);
  const cancelDelete = () => setDeleteConfirm(null);

  const handleDelete = async () => {
    const idx = deleteConfirm;
    setDeleteConfirm(null);
    try {
      await axios.delete(`${API_BASE_URL}/faqs/${idx}`, { headers: getAuthHeaders() });
      showToast('success', 'FAQ berhasil dihapus');
      fetchFAQs();
    } catch (e) {
      showToast('error', e.response?.data?.detail || 'Gagal menghapus FAQ');
    }
  };

  return (
    <div className="management-view">
      {/* Toast */}
      {toast && (
        <div className={`admin-toast admin-toast--${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
          {toast.msg}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm !== null && (
        <div className="confirm-modal-overlay">
          <div className="confirm-modal">
            <AlertTriangle size={36} className="confirm-icon warn" />
            <h3>Hapus FAQ?</h3>
            <p className="confirm-question">"{faqs[deleteConfirm]?.question}"</p>
            <p>Tindakan ini tidak dapat dibatalkan.</p>
            <div className="confirm-btns">
              <button className="btn-cancel-confirm" onClick={cancelDelete}>Batal</button>
              <button className="btn-confirm-delete" onClick={handleDelete}>Ya, Hapus</button>
            </div>
          </div>
        </div>
      )}

      <div className="view-header">
        <h2>FAQ Management <span className="count-badge">{faqs.length} entri</span></h2>
        {formMode === null && (
          <button className="add-btn" onClick={openAdd}>
            <Plus size={18} />
            <span>Tambah FAQ</span>
          </button>
        )}
      </div>

      {/* Add Form — only shown at top when adding new */}
      {formMode === 'add' && (
        <div className="faq-form-card">
          <h3>➕ Tambah FAQ Baru</h3>
          <div className="faq-form-field">
            <label>Pertanyaan <span className="required">*</span></label>
            <textarea
              rows={2}
              placeholder="Masukkan pertanyaan..."
              value={formData.question}
              onChange={e => setFormData(p => ({ ...p, question: e.target.value }))}
            />
          </div>
          <div className="faq-form-field">
            <label>Jawaban <span className="required">*</span></label>
            <textarea
              rows={5}
              placeholder="Masukkan jawaban lengkap..."
              value={formData.answer}
              onChange={e => setFormData(p => ({ ...p, answer: e.target.value }))}
            />
          </div>
          <div className="faq-form-actions">
            <button className="btn-secondary" onClick={cancelForm} disabled={saving}>
              <XCircle size={16} /> Batal
            </button>
            <button className="btn-primary" onClick={handleSave} disabled={saving}>
              {saving ? <RefreshCw size={16} className="spin" /> : <Save size={16} />}
              {saving ? 'Menyimpan...' : 'Simpan'}
            </button>
          </div>
        </div>
      )}

      {/* FAQ List */}
      {loading ? (
        <div className="loading-state"><RefreshCw size={28} className="spin" /><p>Memuat FAQ...</p></div>
      ) : faqs.length === 0 ? (
        <div className="empty-state-box">
          <MessageSquare size={48} />
          <h3>Belum ada FAQ</h3>
          <p>Klik "Tambah FAQ" untuk membuat entri pertama</p>
        </div>
      ) : (
        <div className="faq-list">
          {faqs.map((faq, idx) => (
            <React.Fragment key={idx}>
              <div className={`faq-item ${formMode === 'edit' && editIndex === idx ? 'faq-item-editing' : ''}`}>
                <div className="faq-index">#{idx + 1}</div>
                <div className="faq-content">
                  <div className="faq-question">
                    <span className="faq-label">Q</span>
                    {faq.question}
                  </div>
                  <div className="faq-answer">
                    <span className="faq-label answer-label">A</span>
                    {faq.answer
                      ? (faq.answer.length > 180 ? faq.answer.substring(0, 180) + '…' : faq.answer)
                      : <em style={{ color: 'rgba(255,255,255,0.4)' }}>Belum ada jawaban</em>
                    }
                  </div>
                </div>
                <div className="faq-item-actions">
                  <button
                    className={`btn-edit ${formMode === 'edit' && editIndex === idx ? 'btn-edit-active' : ''}`}
                    title={formMode === 'edit' && editIndex === idx ? 'Sedang diedit' : 'Edit'}
                    onClick={() => formMode === 'edit' && editIndex === idx ? cancelForm() : openEdit(idx)}
                  >
                    {formMode === 'edit' && editIndex === idx ? <XCircle size={15} /> : <Edit size={15} />}
                  </button>
                  <button className="btn-delete" title="Hapus" onClick={() => confirmDelete(idx)}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              {/* Inline Edit Form — appears directly below the item being edited */}
              {formMode === 'edit' && editIndex === idx && (
                <div className="faq-form-card faq-form-inline">
                  <h3>✏️ Edit FAQ #{idx + 1}</h3>
                  <div className="faq-form-field">
                    <label>Pertanyaan <span className="required">*</span></label>
                    <textarea
                      rows={2}
                      placeholder="Masukkan pertanyaan..."
                      value={formData.question}
                      onChange={e => setFormData(p => ({ ...p, question: e.target.value }))}
                      autoFocus
                    />
                  </div>
                  <div className="faq-form-field">
                    <label>Jawaban <span className="required">*</span></label>
                    <textarea
                      rows={5}
                      placeholder="Masukkan jawaban lengkap..."
                      value={formData.answer}
                      onChange={e => setFormData(p => ({ ...p, answer: e.target.value }))}
                    />
                  </div>
                  <div className="faq-form-actions">
                    <button className="btn-secondary" onClick={cancelForm} disabled={saving}>
                      <XCircle size={16} /> Batal
                    </button>
                    <button className="btn-primary" onClick={handleSave} disabled={saving}>
                      {saving ? <RefreshCw size={16} className="spin" /> : <Save size={16} />}
                      {saving ? 'Menyimpan...' : 'Simpan'}
                    </button>
                  </div>
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
};

// Cache Control Component — view stats + hard-wipe with double confirmation
const CacheControl = ({ getAuthHeaders, stats, onRefresh }) => {
  const [cacheStats, setCacheStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showWipeModal, setShowWipeModal] = useState(false);
  const [confirmInput, setConfirmInput] = useState('');
  const [wiping, setWiping] = useState(false);
  const [wipeResult, setWipeResult] = useState(null);
  const [toast, setToast] = useState(null);

  const CONFIRM_PHRASE = 'HAPUS CACHE';

  const showToast = (type, msg) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchCacheStats = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE_URL}/stats`);
      setCacheStats(res.data);
    } catch (e) {
      showToast('error', 'Gagal memuat statistik cache');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCacheStats(); }, []);

  const openWipe = () => {
    setConfirmInput('');
    setWipeResult(null);
    setShowWipeModal(true);
  };

  const closeWipe = () => {
    setShowWipeModal(false);
    setConfirmInput('');
  };

  const handleWipe = async () => {
    if (confirmInput !== CONFIRM_PHRASE) return;
    setWiping(true);
    try {
      const res = await axios.delete(`${API_BASE_URL}/admin/cache/kv/wipe`, {
        headers: getAuthHeaders(),
        data: { confirm_text: confirmInput },
      });
      setWipeResult(res.data);
      showToast('success', res.data.message);
      fetchCacheStats();
      if (onRefresh) onRefresh();
    } catch (e) {
      showToast('error', e.response?.data?.detail || 'Gagal menghapus cache');
    } finally {
      setWiping(false);
      setShowWipeModal(false);
      setConfirmInput('');
    }
  };

  // Lifecycle policy state — persisted in localStorage
  const LC_KEY = 'toba_lc_settings';
  const [lcSettings, setLcSettings] = useState(() => {
    try {
      const saved = localStorage.getItem(LC_KEY);
      return saved ? JSON.parse(saved) : { max_age_days: 21, max_entries: 500, min_access: 5 };
    } catch { return { max_age_days: 21, max_entries: 500, min_access: 5 }; }
  });
  const [lcPreview, setLcPreview]   = useState(null);
  const [lcRunning, setLcRunning]   = useState(false);
  const [lcSaved,   setLcSaved]     = useState(false);
  const [lcResult,  setLcResult]    = useState(null);

  const handleSaveSettings = () => {
    try {
      localStorage.setItem(LC_KEY, JSON.stringify(lcSettings));
      setLcSaved(true);
      setTimeout(() => setLcSaved(false), 2500);
      showToast('success', 'Kebijakan lifecycle berhasil disimpan');
    } catch {
      showToast('error', 'Gagal menyimpan pengaturan');
    }
  };

  const handleLifecyclePreview = async () => {
    setLcRunning('preview');
    setLcPreview(null);
    setLcResult(null);
    try {
      const { max_age_days, max_entries, min_access } = lcSettings;
      const res = await axios.get(`${API_BASE_URL}/admin/cache/lifecycle`, {
        params: { max_age_days, max_entries, min_access },
        headers: getAuthHeaders(),
      });
      setLcPreview(res.data.report);
    } catch (e) {
      showToast('error', e.response?.data?.detail || 'Gagal preview lifecycle');
    } finally {
      setLcRunning(false);
    }
  };

  const handleLifecycleExecute = async () => {
    setLcRunning('execute');
    setLcResult(null);
    try {
      const res = await axios.post(
        `${API_BASE_URL}/admin/cache/lifecycle/execute`,
        lcSettings,
        { headers: getAuthHeaders() },
      );
      setLcResult(res.data);
      setLcPreview(null);
      showToast('success', res.data.message);
      fetchCacheStats();
      if (onRefresh) onRefresh();
    } catch (e) {
      showToast('error', e.response?.data?.detail || 'Gagal eksekusi lifecycle');
    } finally {
      setLcRunning(false);
    }
  };

  const kvStats = cacheStats?.kv_cache || {};
  const confirmed = kvStats.size ?? 0;
  const staging   = kvStats.staging_items ?? 0;
  const total     = confirmed + staging;

  const formatCacheSize = (sizeMb) => {
    if (sizeMb == null) return { value: '—', unit: '' };
    if (sizeMb < 0.001)  return { value: Math.round(sizeMb * 1024 * 1024), unit: 'B' };
    if (sizeMb < 1)      return { value: (sizeMb * 1024).toFixed(2),        unit: 'KB' };
    return               { value: sizeMb.toFixed(2),                         unit: 'MB' };
  };
  const cacheSize = formatCacheSize(kvStats.size_mb);

  return (
    <div className="management-view">
      {/* Toast */}
      {toast && (
        <div className={`admin-toast admin-toast--${toast.type}`}>
          {toast.type === 'success' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
          {toast.msg}
        </div>
      )}

      {/* Hard-Wipe Confirmation Modal */}
      {showWipeModal && (
        <div className="confirm-modal-overlay">
          <div className="confirm-modal wipe-modal">
            <div className="wipe-danger-header">
              <ShieldAlert size={40} className="wipe-danger-icon" />
              <h3>Hapus Seluruh KV Cache</h3>
            </div>

            <div className="wipe-stats-preview">
              <div className="wipe-stat">
                <span className="wipe-stat-val">{confirmed}</span>
                <span className="wipe-stat-lbl">Confirmed cache</span>
              </div>
              <div className="wipe-stat">
                <span className="wipe-stat-val">{staging}</span>
                <span className="wipe-stat-lbl">Staging cache</span>
              </div>
              <div className="wipe-stat wipe-stat--total">
                <span className="wipe-stat-val">{total}</span>
                <span className="wipe-stat-lbl">Total akan dihapus</span>
              </div>
            </div>

            <div className="wipe-warning-box">
              <AlertTriangle size={16} />
              <p>
                Semua respons yang tersimpan di cache akan <strong>hilang permanen</strong>.
                Chatbot harus membuat ulang semua jawaban dari RAG / LLM.
              </p>
            </div>

            <div className="wipe-confirm-input">
              <label>Ketikkan <code className="phrase-code">{CONFIRM_PHRASE}</code> untuk mengonfirmasi:</label>
              <input
                type="text"
                value={confirmInput}
                onChange={e => setConfirmInput(e.target.value)}
                placeholder={CONFIRM_PHRASE}
                className={`wipe-input ${confirmInput === CONFIRM_PHRASE ? 'valid' : confirmInput.length > 0 ? 'invalid' : ''}`}
                autoFocus
              />
              {confirmInput.length > 0 && confirmInput !== CONFIRM_PHRASE && (
                <span className="wipe-input-hint">⚠ Teks tidak cocok</span>
              )}
            </div>

            <div className="confirm-btns">
              <button className="btn-cancel-confirm" onClick={closeWipe} disabled={wiping}>
                <XCircle size={16} /> Batal
              </button>
              <button
                className="btn-confirm-wipe"
                onClick={handleWipe}
                disabled={confirmInput !== CONFIRM_PHRASE || wiping}
              >
                {wiping
                  ? <><RefreshCw size={16} className="spin" /> Menghapus...</>
                  : <><Trash2 size={16} /> Hapus Semua Cache</>
                }
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="view-header">
        <h2>Cache Control</h2>
        <button className="refresh-btn" onClick={fetchCacheStats} disabled={loading}>
          <RefreshCw size={18} className={loading ? 'spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="cache-stats-grid">
        <div className="cache-stat-card">
          <Database size={28} className="cache-card-icon blue" />
          <div>
            <div className="cache-stat-number">{confirmed}</div>
            <div className="cache-stat-label">Confirmed Cache</div>
            <div className="cache-stat-sub">Sudah diverifikasi via feedback</div>
          </div>
        </div>
        <div className="cache-stat-card">
          <Clock size={28} className="cache-card-icon orange" />
          <div>
            <div className="cache-stat-number">{staging}</div>
            <div className="cache-stat-label">Staging Cache</div>
            <div className="cache-stat-sub">Menunggu verifikasi pengguna</div>
          </div>
        </div>
        <div className="cache-stat-card">
          <Activity size={28} className="cache-card-icon green" />
          <div>
            <div className="cache-stat-number">{cacheSize.value} <span className="cache-size-unit">{cacheSize.unit}</span></div>
            <div className="cache-stat-label">Ukuran Cache</div>
            <div className="cache-stat-sub">Total penyimpanan digunakan</div>
          </div>
        </div>
        <div className="cache-stat-card">
          <TrendingUp size={28} className="cache-card-icon purple" />
          <div>
            <div className="cache-stat-number">
              {cacheStats?.kv_cache?.cache_hit_rate != null
                ? `${(cacheStats.kv_cache.cache_hit_rate * 100).toFixed(1)}%`
                : '—'}
            </div>
            <div className="cache-stat-label">Cache Hit Rate</div>
            <div className="cache-stat-sub">Efisiensi cache saat ini</div>
          </div>
        </div>
      </div>

      {/* Last wipe result */}
      {wipeResult && (
        <div className="wipe-result-box">
          <CheckCircle size={20} />
          <span>{wipeResult.message}</span>
        </div>
      )}

      {/* Lifecycle Policy */}
      <div className="lifecycle-zone">
        <div className="lifecycle-header">
          <Clock size={20} />
          <h3>Kebijakan Lifecycle Cache</h3>
        </div>
        <div className="lifecycle-body">

          {/* Settings */}
          <div className="lifecycle-settings">

            {/* Max age */}
            <div className="lc-setting">
              <label>Umur Maksimum (hari)</label>
              <p className="lc-hint">Entry tidak diakses selama ini akan jadi kandidat hapus (jika akses juga rendah)</p>
              <div className="lc-presets">
                {[{v:1,l:'1 Hari'},{v:7,l:'1 Minggu'},{v:21,l:'3 Minggu'},{v:30,l:'1 Bulan'}].map(({v,l}) => (
                  <button key={v}
                    className={`btn-preset ${lcSettings.max_age_days === v ? 'active' : ''}`}
                    onClick={() => setLcSettings(s => ({...s, max_age_days: v}))}>
                    {l}
                  </button>
                ))}
              </div>
              <input type="number" min={1} max={365} value={lcSettings.max_age_days}
                onChange={e => setLcSettings(s => ({...s, max_age_days: +e.target.value}))}
                className="lc-input" />
            </div>

            {/* Max entries */}
            <div className="lc-setting">
              <label>Batas Jumlah Entry Cache</label>
              <p className="lc-hint">Jika jumlah entry melebihi ini, entry paling jarang diakses akan di-evict lebih dulu. Isi 0 untuk tidak dibatasi.</p>
              <input type="number" min={0} max={10000} value={lcSettings.max_entries}
                onChange={e => setLcSettings(s => ({...s, max_entries: +e.target.value}))}
                className="lc-input" />
            </div>

            {/* Min access */}
            <div className="lc-setting">
              <label>Minimum Akses untuk Dipertahankan</label>
              <p className="lc-hint">Entry dengan jumlah akses kurang dari ini DAN sudah melewati umur maksimum akan dihapus otomatis</p>
              <input type="number" min={1} max={100} value={lcSettings.min_access}
                onChange={e => setLcSettings(s => ({...s, min_access: +e.target.value}))}
                className="lc-input" />
            </div>
          </div>

          {/* Actions */}
          <div className="lc-actions">
            <button className="btn-preview" onClick={handleLifecyclePreview} disabled={!!lcRunning}>
              {lcRunning === 'preview'
                ? <><RefreshCw size={16} className="spin" /> Memuat...</>
                : <><Eye size={16} /> Preview (Dry-run)</>
              }
            </button>
            <button className="btn-save-lc" onClick={handleSaveSettings} disabled={!!lcRunning}>
              {lcSaved
                ? <><CheckCircle size={16} /> Tersimpan!</>
                : <><Save size={16} /> Simpan Kebijakan</>
              }
            </button>
          </div>

          {/* Preview result */}
          {lcPreview && (
            <div className="lc-preview-box">
              <h4><Eye size={15} /> Hasil Preview — belum dieksekusi</h4>
              <div className="lc-preview-stats">
                <span className="lc-stat lc-stat--delete">🗑️ Akan Dihapus <strong>{lcPreview.summary?.to_delete ?? 0}</strong></span>
                <span className="lc-stat lc-stat--promote">⭐ Dipromosi ke FAQ <strong>{lcPreview.summary?.to_promote ?? 0}</strong></span>
                <span className="lc-stat lc-stat--keep">✅ Tetap Disimpan <strong>{lcPreview.summary?.to_keep ?? 0}</strong></span>
                <span className="lc-stat lc-stat--staging">📋 Staging Evict <strong>{lcPreview.summary?.staging_evict ?? 0}</strong></span>
              </div>
              <button className="btn-execute-lc" onClick={handleLifecycleExecute} disabled={!!lcRunning}>
                {lcRunning === 'execute'
                  ? <><RefreshCw size={16} className="spin" /> Memproses...</>
                  : <><Play size={16} /> Jalankan Lifecycle Sekarang</>
                }
              </button>
            </div>
          )}

          {/* Execute result */}
          {lcResult && (
            <div className="lc-result-box">
              <CheckCircle size={18} />
              <span>{lcResult.message}</span>
            </div>
          )}
        </div>
      </div>

      {/* Danger Zone */}
      <div className="danger-zone">
        <div className="danger-zone-header">
          <ShieldAlert size={22} />
          <h3>Danger Zone</h3>
        </div>
        <div className="danger-zone-body">
          <div className="danger-action">
            <div className="danger-action-info">
              <strong>Hapus Seluruh KV Cache</strong>
              <p>
                Menghapus <strong>semua</strong> respons yang tersimpan — baik confirmed maupun staging.
                Chatbot akan memperlambat sementara karena harus regenerasi ulang dari RAG/LLM.
              </p>
            </div>
            <button className="btn-danger" onClick={openWipe}>
              <Trash2 size={18} />
              Hapus Cache
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};



// Analytics View Component
const AnalyticsView = ({ getAuthHeaders }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAnalytics = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const resp = await axios.get(`${API_BASE_URL}/admin/analytics?limit=50`, {
        headers: getAuthHeaders(),
      });
      setData(resp.data);
      setError(null);
    } catch (e) {
      setError('Gagal memuat data analytics');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchAnalytics(); }, []);

  const fmtMs = (ms) => {
    if (ms == null) return '—';
    return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
  };

  const sourceLabel = (src) => {
    if (src === 'cag_cache') return <span className="src-badge src-cag">CAG ⚡</span>;
    if (src === 'rag') return <span className="src-badge src-rag">RAG 🔍</span>;
    return <span className="src-badge src-other">{src || '—'}</span>;
  };

  const ratingIcon = (r) => {
    if (r == null) return <span className="rating-none">—</span>;
    if (r > 0) return <span className="rating-like">👍</span>;
    if (r < 0) return <span className="rating-dislike">👎</span>;
    return <span className="rating-none">—</span>;
  };

  if (loading) return (
    <div className="analytics-loading">
      <RefreshCw size={28} className="spin-icon" />
      <p>Memuat data analytics...</p>
    </div>
  );

  if (error) return (
    <div className="analytics-error">
      <p>{error}</p>
      <button className="btn-refresh-analytics" onClick={() => fetchAnalytics()}>Coba Lagi</button>
    </div>
  );

  const cag = data?.latency?.cag_cache;
  const rag = data?.latency?.rag;
  const hr = data?.hit_rate;
  const acc = data?.accuracy;
  const maxAvg = Math.max(cag?.avg_ms || 0, rag?.avg_ms || 0) || 1;

  return (
    <div className="research-analytics">
      {/* Header */}
      <div className="ra-header">
        <div>
          <h2>Research Analytics</h2>
          <p className="ra-subtitle">Perbandingan performa CAG vs RAG dari data nyata pengguna</p>
        </div>
        <button
          className="btn-refresh-analytics"
          onClick={() => fetchAnalytics(true)}
          disabled={refreshing}
        >
          <RefreshCw size={15} className={refreshing ? 'spin-icon' : ''} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="ra-summary-cards">
        <div className="ra-card">
          <span className="ra-card-value">{hr?.total ?? 0}</span>
          <span className="ra-card-label">Total Query</span>
        </div>
        <div className="ra-card ra-card-cag">
          <span className="ra-card-value">{hr?.cag_hits ?? 0}</span>
          <span className="ra-card-label">CAG Hits ⚡</span>
        </div>
        <div className="ra-card ra-card-rag">
          <span className="ra-card-value">{hr?.rag_hits ?? 0}</span>
          <span className="ra-card-label">RAG Calls 🔍</span>
        </div>
        <div className="ra-card ra-card-rate">
          <span className="ra-card-value">{hr?.hit_rate_pct ?? 0}%</span>
          <span className="ra-card-label">Cache Hit Rate</span>
        </div>
        <div className="ra-card ra-card-acc">
          <span className="ra-card-value">{acc?.like_rate_pct ?? 0}%</span>
          <span className="ra-card-label">Akurasi (👍 Rate)</span>
        </div>
        <div className="ra-card">
          <span className="ra-card-value">{acc?.total_feedback ?? 0}</span>
          <span className="ra-card-label">Total Feedback</span>
        </div>
      </div>

      {/* Latency Comparison */}
      <div className="ra-section">
        <h3 className="ra-section-title">Perbandingan Latensi CAG vs RAG</h3>
        <div className="latency-compare">
          {[['cag_cache', 'CAG ⚡', cag, 'lc-bar-cag'], ['rag', 'RAG 🔍', rag, 'lc-bar-rag']].map(([key, label, d, cls]) => (
            <div key={key} className="lc-row">
              <div className="lc-row-label">{label}</div>
              <div className="lc-bar-wrap">
                <div
                  className={`lc-bar ${cls}`}
                  style={{ width: d ? `${Math.max(4, (d.avg_ms / maxAvg) * 100)}%` : '4%' }}
                >
                  {d ? fmtMs(d.avg_ms) : '—'}
                </div>
              </div>
              <div className="lc-meta">
                {d ? (
                  <>
                    <span>Min: {fmtMs(d.min_ms)}</span>
                    <span>Max: {fmtMs(d.max_ms)}</span>
                    <span>{d.count} query</span>
                  </>
                ) : <span>Belum ada data</span>}
              </div>
            </div>
          ))}
        </div>
        {cag && rag && (
          <p className="lc-insight">
            💡 CAG rata-rata{' '}
            {rag.avg_ms > cag.avg_ms
              ? <strong>{fmtMs(rag.avg_ms - cag.avg_ms)} lebih cepat</strong>
              : <strong>{fmtMs(cag.avg_ms - rag.avg_ms)} lebih lambat</strong>}{' '}
            dibanding RAG
          </p>
        )}
      </div>

      {/* Accuracy by Source */}
      {acc?.by_source && Object.keys(acc.by_source).length > 0 && (
        <div className="ra-section">
          <h3 className="ra-section-title">Akurasi per Sumber (dari Feedback)</h3>
          <div className="accuracy-grid">
            {Object.entries(acc.by_source).map(([src, d]) => (
              <div key={src} className={`acc-card ${src === 'cag_cache' ? 'acc-cag' : 'acc-rag'}`}>
                <div className="acc-card-title">{src === 'cag_cache' ? 'CAG ⚡' : 'RAG 🔍'}</div>
                <div className="acc-rate">{d.like_rate_pct}%</div>
                <div className="acc-details">
                  <span>👍 {d.likes}</span>
                  <span>👎 {d.dislikes}</span>
                  <span>Total {d.total}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Daily Hit Rate Trend */}
      {hr?.daily && hr.daily.length > 0 && (
        <div className="ra-section">
          <h3 className="ra-section-title">Tren Cache Hit Rate (30 Hari Terakhir)</h3>
          <div className="hit-trend">
            {hr.daily.map((d) => (
              <div key={d.date} className="ht-col">
                <div
                  className="ht-bar"
                  style={{ height: `${Math.max(4, d.rate)}%` }}
                  title={`${d.date}: ${d.rate}% (${d.hits}/${d.total})`}
                />
                <span className="ht-label">{d.date?.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-Query Table */}
      <div className="ra-section">
        <h3 className="ra-section-title">50 Query Terakhir</h3>
        <div className="query-table-wrap">
          <table className="query-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Penanya</th>
                <th>Pertanyaan</th>
                <th>Jawaban</th>
                <th>Sumber</th>
                <th>Latensi</th>
                <th>Feedback</th>
                <th>Waktu</th>
              </tr>
            </thead>
            <tbody>
              {(data?.recent_queries || []).map((q, i) => (
                <tr key={q.id}>
                  <td className="qt-num">{i + 1}</td>
                  <td className="qt-user" title={q.asked_by || 'Guest'}>{q.asked_by || 'Guest'}</td>
                  <td className="qt-question" title={q.question}>{q.question}</td>
                  <td className="qt-answer" title={q.answer || '—'}>{q.answer || '—'}</td>
                  <td>{sourceLabel(q.source)}</td>
                  <td className="qt-latency">{fmtMs(q.response_time_ms)}</td>
                  <td className="qt-rating">{ratingIcon(q.rating)}</td>
                  <td className="qt-time">{q.created_at ? new Date(q.created_at).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// Settings View Component
const SettingsView = ({ user }) => {
  return (
    <div className="settings-view">
      <div className="settings-section">
        <h3>Profile Settings</h3>
        <div className="settings-form">
          <div className="form-group">
            <label>Username</label>
            <input type="text" value={user?.username || ''} disabled />
          </div>
          <div className="form-group">
            <label>Name</label>
            <input type="text" defaultValue={user?.name || ''} />
          </div>
          <div className="form-group">
            <label>Role</label>
            <input type="text" value={user?.role || ''} disabled />
          </div>
          <button className="save-btn">Save Changes</button>
        </div>
      </div>
      <div className="settings-section">
        <h3>System Settings</h3>
        <div className="settings-form">
          <div className="setting-item">
            <div className="setting-info">
              <span className="setting-name">Auto-refresh Dashboard</span>
              <span className="setting-desc">Automatically refresh data every 30 seconds</span>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" defaultChecked />
              <span className="toggle-slider"></span>
            </label>
          </div>
          <div className="setting-item">
            <div className="setting-info">
              <span className="setting-name">Dark Mode</span>
              <span className="setting-desc">Enable dark mode theme</span>
            </div>
            <label className="toggle-switch">
              <input type="checkbox" defaultChecked />
              <span className="toggle-slider"></span>
            </label>
          </div>
        </div>
      </div>
    </div>
  );
};

// Users Management Component
const UsersManagement = ({ getAllUsers }) => {
  const [users, setUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const usersResult = await Promise.resolve(getAllUsers());
        setUsers(usersResult || []);
      } catch (error) {
        console.error('Error fetching users:', error);
        setUsers([]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [getAllUsers]);

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('id-ID', { 
      day: '2-digit', 
      month: 'short', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getRoleBadgeClass = (role) => {
    switch (role) {
      case 'admin': return 'badge-admin';
      case 'operator': return 'badge-operator';
      default: return 'badge-user';
    }
  };

  if (loading) {
    return (
      <div className="users-management">
        <div className="loading-state">
          <RefreshCw size={32} className="spin" />
          <p>Memuat data pengguna...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="users-management">
      <div className="users-list-section">
          <div className="users-table-container">
            {users.length === 0 ? (
              <div className="empty-state-box">
                <Users size={48} />
                <h3>Belum Ada User Terdaftar</h3>
                <p>User akan muncul di sini setelah mereka mendaftar</p>
              </div>
            ) : (
            <>
            {/* Desktop Table View */}
            <table className="users-table">
              <thead>
                <tr>
                  <th>Avatar</th>
                  <th>Username</th>
                  <th>Nama</th>
                  <th>Role</th>
                  <th>Chat</th>
                  <th>Terakhir Aktif</th>
                  <th>Terdaftar</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr 
                    key={u.id} 
                    className={selectedUser?.id === u.id ? 'selected' : ''}
                    onClick={() => setSelectedUser(u)}
                  >
                    <td>
                      <div className="user-avatar-cell">
                        <Avatar src={u.avatar} size="small" />
                      </div>
                    </td>
                    <td><strong>{u.username}</strong></td>
                    <td>{u.name || '-'}</td>
                    <td>
                      <span className={`role-badge ${getRoleBadgeClass(u.role)}`}>
                        {u.role}
                      </span>
                    </td>
                    <td>{u.chatCount || 0}</td>
                    <td>{formatDate(u.lastActive)}</td>
                    <td>{formatDate(u.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Mobile Card View */}
            <div className="mobile-users-cards">
              {users.map((u) => (
                <div 
                  key={u.id} 
                  className={`mobile-user-card ${selectedUser?.id === u.id ? 'selected' : ''}`}
                  onClick={() => setSelectedUser(u)}
                >
                  <div className="mobile-user-header">
                    <div className="mobile-user-avatar">
                      <Avatar src={u.avatar} size="medium" />
                    </div>
                    <div className="mobile-user-info">
                      <h4>{u.name || u.username}</h4>
                      <p className="mobile-username">@{u.username}</p>
                      <span className={`role-badge ${getRoleBadgeClass(u.role)}`}>
                        {u.role}
                      </span>
                    </div>
                  </div>
                  <div className="mobile-user-stats">
                    <div className="mobile-stat">
                      <span className="mobile-stat-label">Chat</span>
                      <span className="mobile-stat-value">{u.chatCount || 0}</span>
                    </div>
                    <div className="mobile-stat">
                      <span className="mobile-stat-label">Terakhir Aktif</span>
                      <span className="mobile-stat-value">{formatDate(u.lastActive)}</span>
                    </div>
                    <div className="mobile-stat">
                      <span className="mobile-stat-label">Terdaftar</span>
                      <span className="mobile-stat-value">{formatDate(u.createdAt)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            </>
            )}
          </div>

          {/* User Detail Panel */}
          {selectedUser && (
            <div className="user-detail-panel">
              <div className="user-detail-header">
                <div className="user-detail-avatar">
                  <Avatar src={selectedUser.avatar} size="large" />
                </div>
                <div>
                  <h3>{selectedUser.name || selectedUser.username}</h3>
                  <span className={`role-badge ${getRoleBadgeClass(selectedUser.role)}`}>
                    {selectedUser.role}
                  </span>
                </div>
              </div>
              <div className="user-detail-stats">
                <div className="stat-item">
                  <span className="stat-value">{selectedUser.chatCount || 0}</span>
                  <span className="stat-label">Total Chat</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{formatDate(selectedUser.lastActive)}</span>
                  <span className="stat-label">Terakhir Aktif</span>
                </div>
              </div>
            </div>
          )}
        </div>
    </div>
  );
};

export default AdminDashboard;
