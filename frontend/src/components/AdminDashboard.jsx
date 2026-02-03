import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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
  UserCheck,
  History,
  UserCircle,
  User
} from 'lucide-react';
import './AdminDashboard.css';

const API_BASE_URL = '/api';

const AdminDashboard = () => {
  const { user, logout, getAllUsers, getUserActivity } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState('dashboard');
  const [systemStatus, setSystemStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locations, setLocations] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [isMusicPlaying, setIsMusicPlaying] = useState(false);
  const [musicHasPlayed, setMusicHasPlayed] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const audioRef = useRef(null);
  const userMenuRef = useRef(null);

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
    fetchLocations();
    fetchFAQs();
    const interval = setInterval(() => {
      fetchSystemStatus();
      fetchStats();
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
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'users', label: 'User Management', icon: Users },
    { id: 'locations', label: 'Lokasi Wisata', icon: MapPin },
    { id: 'faqs', label: 'FAQ Management', icon: MessageSquare },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
    { id: 'system', label: 'System Status', icon: Server },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const renderContent = () => {
    switch (activeMenu) {
      case 'dashboard':
        return <DashboardOverview stats={stats} systemStatus={systemStatus} locations={locations} loading={loading} />;
      case 'users':
        return <UsersManagement getAllUsers={getAllUsers} getUserActivity={getUserActivity} />;
      case 'locations':
        return <LocationsManagement locations={locations} />;
      case 'faqs':
        return <FAQManagement faqs={faqs} />;
      case 'analytics':
        return <AnalyticsView stats={stats} />;
      case 'system':
        return <SystemStatusView systemStatus={systemStatus} onRefresh={fetchSystemStatus} />;
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
                setActiveMenu(item.id);
                setMobileMenuOpen(false);
              }}
            >
              <item.icon size={20} />
              {sidebarOpen && <span>{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <Link to="/" className="nav-item home-link">
            <Home size={20} />
            {sidebarOpen && <span>Ke Beranda</span>}
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
                  {user?.avatar || user?.name?.charAt(0) || 'A'}
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
                    to="/profile" 
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
const DashboardOverview = ({ stats, systemStatus, locations, loading }) => {
  const statCards = [
    {
      title: 'Total Queries',
      value: stats?.total_queries || 0,
      icon: MessageSquare,
      color: 'blue',
      trend: '+12%'
    },
    {
      title: 'Cache Hit Rate',
      value: stats?.cache_hit_rate ? `${(stats.cache_hit_rate * 100).toFixed(1)}%` : '0%',
      icon: Database,
      color: 'green',
      trend: '+5%'
    },
    {
      title: 'Avg Response Time',
      value: stats?.avg_response_time ? `${stats.avg_response_time.toFixed(2)}s` : '0s',
      icon: Clock,
      color: 'purple',
      trend: '-8%'
    },
    {
      title: 'Lokasi Wisata',
      value: locations?.length || 0,
      icon: MapPin,
      color: 'orange',
      trend: '+2'
    }
  ];

  return (
    <div className="dashboard-overview">
      {/* Stat Cards */}
      <div className="stat-cards">
        {statCards.map((stat, index) => (
          <div key={index} className={`stat-card ${stat.color}`}>
            <div className="stat-icon">
              <stat.icon size={24} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{loading ? '...' : stat.value}</span>
              <span className="stat-label">{stat.title}</span>
            </div>
            <div className="stat-trend positive">
              <TrendingUp size={16} />
              <span>{stat.trend}</span>
            </div>
          </div>
        ))}
      </div>

      {/* System Status Cards */}
      <div className="dashboard-grid">
        <div className="dashboard-card system-health">
          <div className="card-header">
            <h3>System Health</h3>
            <span className={`status-badge ${systemStatus?.status === 'healthy' ? 'healthy' : 'warning'}`}>
              {systemStatus?.status === 'healthy' ? (
                <><CheckCircle size={14} /> Healthy</>
              ) : (
                <><AlertTriangle size={14} /> Warning</>
              )}
            </span>
          </div>
          <div className="health-items">
            <div className="health-item">
              <Server size={18} />
              <span>Model Status</span>
              <span className={`health-status ${systemStatus?.model_loaded ? 'active' : 'inactive'}`}>
                {systemStatus?.model_loaded ? 'Loaded' : 'Not Loaded'}
              </span>
            </div>
            <div className="health-item">
              <Database size={18} />
              <span>KV Cache</span>
              <span className="health-status active">
                {stats?.kv_cache_entries || 0} entries
              </span>
            </div>
            <div className="health-item">
              <Activity size={18} />
              <span>Uptime</span>
              <span className="health-status active">
                {systemStatus?.uptime || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        <div className="dashboard-card recent-activity">
          <div className="card-header">
            <h3>Recent Activity</h3>
            <button className="view-all-btn">View All <ChevronRight size={16} /></button>
          </div>
          <div className="activity-list">
            <div className="activity-item">
              <div className="activity-icon blue">
                <MessageSquare size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">New query received</span>
                <span className="activity-time">2 minutes ago</span>
              </div>
            </div>
            <div className="activity-item">
              <div className="activity-icon green">
                <Database size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">Cache updated</span>
                <span className="activity-time">15 minutes ago</span>
              </div>
            </div>
            <div className="activity-item">
              <div className="activity-icon purple">
                <FileText size={16} />
              </div>
              <div className="activity-info">
                <span className="activity-text">FAQ entry added</span>
                <span className="activity-time">1 hour ago</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="quick-actions">
        <h3>Quick Actions</h3>
        <div className="action-buttons">
          <button className="action-btn">
            <RefreshCw size={20} />
            <span>Refresh Cache</span>
          </button>
          <button className="action-btn">
            <MapPin size={20} />
            <span>Add Location</span>
          </button>
          <button className="action-btn">
            <MessageSquare size={20} />
            <span>Add FAQ</span>
          </button>
          <button className="action-btn">
            <FileText size={20} />
            <span>View Logs</span>
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

// FAQ Management Component
const FAQManagement = ({ faqs }) => {
  return (
    <div className="management-view">
      <div className="view-header">
        <h2>FAQ Management</h2>
        <button className="add-btn">
          <MessageSquare size={18} />
          <span>Tambah FAQ</span>
        </button>
      </div>
      <div className="faq-list">
        {faqs.length > 0 ? (
          faqs.slice(0, 10).map((faq, index) => (
            <div key={index} className="faq-item">
              <div className="faq-question">
                <strong>Q:</strong> {faq.question}
              </div>
              <div className="faq-answer">
                <strong>A:</strong> {faq.answer?.substring(0, 200)}...
              </div>
              <div className="faq-actions">
                <button className="btn-edit">Edit</button>
                <button className="btn-delete">Delete</button>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state">Tidak ada data FAQ</div>
        )}
      </div>
    </div>
  );
};

// Analytics View Component
const AnalyticsView = ({ stats }) => {
  return (
    <div className="analytics-view">
      <div className="analytics-cards">
        <div className="analytics-card">
          <h3>Query Statistics</h3>
          <div className="analytics-stat">
            <span className="stat-number">{stats?.total_queries || 0}</span>
            <span className="stat-label">Total Queries</span>
          </div>
          <div className="analytics-stat">
            <span className="stat-number">{stats?.today_queries || 0}</span>
            <span className="stat-label">Today</span>
          </div>
        </div>
        <div className="analytics-card">
          <h3>Response Performance</h3>
          <div className="analytics-stat">
            <span className="stat-number">{stats?.avg_response_time?.toFixed(2) || 0}s</span>
            <span className="stat-label">Avg Response Time</span>
          </div>
          <div className="analytics-stat">
            <span className="stat-number">{stats?.min_response_time?.toFixed(2) || 0}s</span>
            <span className="stat-label">Fastest</span>
          </div>
        </div>
        <div className="analytics-card">
          <h3>Cache Performance</h3>
          <div className="analytics-stat">
            <span className="stat-number">{((stats?.cache_hit_rate || 0) * 100).toFixed(1)}%</span>
            <span className="stat-label">Hit Rate</span>
          </div>
          <div className="analytics-stat">
            <span className="stat-number">{stats?.kv_cache_entries || 0}</span>
            <span className="stat-label">Cache Entries</span>
          </div>
        </div>
      </div>
    </div>
  );
};

// System Status View Component
const SystemStatusView = ({ systemStatus, onRefresh }) => {
  return (
    <div className="system-view">
      <div className="view-header">
        <h2>System Status</h2>
        <button className="refresh-btn" onClick={onRefresh}>
          <RefreshCw size={18} />
          <span>Refresh</span>
        </button>
      </div>
      <div className="system-info-grid">
        <div className="system-info-card">
          <h4>Model Information</h4>
          <div className="info-row">
            <span>Model Name:</span>
            <span>{systemStatus?.model_name || 'N/A'}</span>
          </div>
          <div className="info-row">
            <span>Model Loaded:</span>
            <span className={systemStatus?.model_loaded ? 'status-active' : 'status-inactive'}>
              {systemStatus?.model_loaded ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="info-row">
            <span>Device:</span>
            <span>{systemStatus?.device || 'N/A'}</span>
          </div>
        </div>
        <div className="system-info-card">
          <h4>Cache Status</h4>
          <div className="info-row">
            <span>KV Cache Entries:</span>
            <span>{systemStatus?.kv_cache_entries || 0}</span>
          </div>
          <div className="info-row">
            <span>Summary Cache Entries:</span>
            <span>{systemStatus?.summary_cache_entries || 0}</span>
          </div>
        </div>
        <div className="system-info-card">
          <h4>System Health</h4>
          <div className="info-row">
            <span>Status:</span>
            <span className={systemStatus?.status === 'healthy' ? 'status-active' : 'status-warning'}>
              {systemStatus?.status || 'Unknown'}
            </span>
          </div>
          <div className="info-row">
            <span>Uptime:</span>
            <span>{systemStatus?.uptime || 'N/A'}</span>
          </div>
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
const UsersManagement = ({ getAllUsers, getUserActivity }) => {
  const [users, setUsers] = useState([]);
  const [activities, setActivities] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // getAllUsers might be async or sync, handle both
        const usersResult = await Promise.resolve(getAllUsers());
        setUsers(usersResult || []);
        
        // getUserActivity is sync
        const activitiesResult = getUserActivity(50);
        setActivities(activitiesResult || []);
      } catch (error) {
        console.error('Error fetching users:', error);
        setUsers([]);
        setActivities([]);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [getAllUsers, getUserActivity]);

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

  const getActionIcon = (action) => {
    switch (action) {
      case 'login': return '🔓';
      case 'logout': return '🔒';
      case 'register': return '✨';
      case 'chat': return '💬';
      case 'session_restored': return '🔄';
      default: return '📌';
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
      {/* Tabs */}
      <div className="users-tabs">
        <button 
          className={`tab-btn ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <UserCheck size={18} />
          <span>Daftar User ({users.length})</span>
        </button>
        <button 
          className={`tab-btn ${activeTab === 'activity' ? 'active' : ''}`}
          onClick={() => setActiveTab('activity')}
        >
          <History size={18} />
          <span>Activity Log</span>
        </button>
      </div>

      {activeTab === 'users' ? (
        <div className="users-list-section">
          <div className="users-table-container">
            {users.length === 0 ? (
              <div className="empty-state-box">
                <Users size={48} />
                <h3>Belum Ada User Terdaftar</h3>
                <p>User akan muncul di sini setelah mereka mendaftar</p>
              </div>
            ) : (
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
                    <td><span className="user-avatar-cell">{u.avatar || '👤'}</span></td>
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
            )}
          </div>

          {/* User Detail Panel */}
          {selectedUser && (
            <div className="user-detail-panel">
              <div className="user-detail-header">
                <span className="user-detail-avatar">{selectedUser.avatar || '👤'}</span>
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
      ) : (
        <div className="activity-log-section">
          <div className="activity-list">
            {activities.length === 0 ? (
              <div className="no-activity">Belum ada aktivitas tercatat</div>
            ) : (
              activities.map((act) => (
                <div key={act.id} className="activity-item">
                  <span className="activity-icon">{getActionIcon(act.action)}</span>
                  <div className="activity-info">
                    <strong>{act.username}</strong>
                    <span className="activity-action">{act.action}</span>
                  </div>
                  <span className="activity-time">{formatDate(act.timestamp)}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
