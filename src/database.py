"""
SQLite Database Manager for Toba Tourism Chatbot
Handles user management, chat history, and session management
"""

import sqlite3
import hashlib
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import os

# Database path
DB_DIR = Path(__file__).parent.parent / "database"
DB_PATH = DB_DIR / "toba_chatbot.db"

def get_db_connection():
    """Create a database connection with row factory"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with all required tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            avatar TEXT DEFAULT '😊',
            role TEXT DEFAULT 'user' CHECK(role IN ('admin', 'operator', 'user')),
            bio TEXT,
            location TEXT,
            favorite_categories TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Sessions table for authentication tokens
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Chat history table (each Q&A turn, linked to a conversation thread)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_id TEXT,
            conversation_id TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT,
            response_time_ms INTEGER,
            model_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
        )
    ''')
    
    # Conversations table — one row per chat thread in the sidebar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            title TEXT DEFAULT 'General',
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Feedback table — NOTE: rating allows -1 (dislike) and +1 (like)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            rating INTEGER CHECK(rating >= -1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (chat_id) REFERENCES chat_history(id) ON DELETE CASCADE
        )
    ''')

    # Run schema migrations FIRST — ensures all columns exist before indexes are built
    conn.commit()
    _migrate_schema(cursor, conn)

    # Create indexes for better performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_history(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_conv ON chat_history(conversation_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)')

    conn.commit()

    # Create default admin user if not exists
    create_default_admin(cursor, conn)

    conn.close()
    print(f"✅ Database initialized at: {DB_PATH}")

def _migrate_schema(cursor, conn):
    """Apply incremental schema migrations to an existing database."""
    # 1. Add conversation_id column to chat_history if not present
    cursor.execute("PRAGMA table_info(chat_history)")
    existing_cols = {row['name'] for row in cursor.fetchall()}
    if 'conversation_id' not in existing_cols:
        cursor.execute('ALTER TABLE chat_history ADD COLUMN conversation_id TEXT')
        print("⬆️  Migration: added chat_history.conversation_id")

    # 2. Fix feedback rating constraint (old DB has CHECK >= 1, dislike=-1 fails)
    #    SQLite does not allow ALTER COLUMN, so we rebuild the table only if needed.
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='feedback'")
    row = cursor.fetchone()
    if row and 'rating >= 1' in (row['sql'] or ''):
        cursor.execute('ALTER TABLE feedback RENAME TO feedback_old')
        cursor.execute('''
            CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                chat_id INTEGER,
                rating INTEGER CHECK(rating >= -1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY (chat_id) REFERENCES chat_history(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('INSERT INTO feedback SELECT * FROM feedback_old')
        cursor.execute('DROP TABLE feedback_old')
        print("⬆️  Migration: rebuilt feedback table (allow rating=-1)")

    # 3. Add message_hash column to feedback for toggle support
    cursor.execute("PRAGMA table_info(feedback)")
    fb_cols = {row['name'] for row in cursor.fetchall()}
    if 'message_hash' not in fb_cols:
        cursor.execute('ALTER TABLE feedback ADD COLUMN message_hash TEXT')
        print("⬆️  Migration: added feedback.message_hash")

    conn.commit()


def create_default_admin(cursor, conn):
    """Create default admin user if not exists"""
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        password_hash = hash_password("Admin#123")
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, name, avatar, role, bio)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('admin', 'admin@tobachatbot', password_hash, 'Administrator', '👨‍💼', 'admin', 'System Administrator'))
        conn.commit()
        print("✅ Default admin user created (email: admin@tobachatbot, password: Admin#123)")

def hash_password(password: str, salt: str = None) -> str:
    """Hash password with salt using SHA-256"""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}${hash_obj.hexdigest()}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    try:
        salt, stored_hash = password_hash.split('$')
        new_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return new_hash == stored_hash
    except:
        return False

def generate_session_token() -> str:
    """Generate a secure session token"""
    return secrets.token_urlsafe(32)

# ============================================
# User Management Functions
# ============================================

def create_user(username: str, email: str, password: str, name: str = None, 
                role: str = 'user', avatar: str = '😊') -> Dict[str, Any]:
    """Create a new user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if username or email exists
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            return {"success": False, "error": "Username atau email sudah terdaftar"}
        
        password_hash = hash_password(password)
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, name, avatar, role)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, password_hash, name or username, avatar, role))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        return {
            "success": True,
            "user_id": user_id,
            "message": "Registrasi berhasil"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def authenticate_user(username: str, password: str, ip_address: str = None, 
                     user_agent: str = None) -> Dict[str, Any]:
    """Authenticate user and create session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, password_hash, name, avatar, role, bio, location, 
                   favorite_categories, is_active, created_at
            FROM users WHERE username = ? OR email = ?
        ''', (username, username))
        
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "error": "Username tidak ditemukan"}
        
        if not user['is_active']:
            return {"success": False, "error": "Akun telah dinonaktifkan"}
        
        if not verify_password(password, user['password_hash']):
            return {"success": False, "error": "Password salah"}
        
        # Create session token
        token = generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        ''', (user['id'], token, expires_at, ip_address, user_agent))
        
        # Update last login
        cursor.execute('''
            UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user['id'],))
        
        conn.commit()
        
        # Parse favorite_categories
        favorite_categories = []
        try:
            favorite_categories = json.loads(user['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email'],
                "name": user['name'],
                "avatar": user['avatar'],
                "role": user['role'],
                "bio": user['bio'],
                "location": user['location'],
                "favoriteCategories": favorite_categories,
                "createdAt": user['created_at']
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """Validate session token and return user data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT s.user_id, s.expires_at, u.id, u.username, u.email, u.name, 
                   u.avatar, u.role, u.bio, u.location, u.favorite_categories, u.is_active
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        ''', (token,))
        
        result = cursor.fetchone()
        
        if not result:
            return None
        
        # Check if expired
        expires_at = datetime.fromisoformat(result['expires_at'])
        if expires_at < datetime.now():
            # Delete expired session
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None
        
        if not result['is_active']:
            return None
        
        favorite_categories = []
        try:
            favorite_categories = json.loads(result['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "id": result['id'],
            "username": result['username'],
            "email": result['email'],
            "name": result['name'],
            "avatar": result['avatar'],
            "role": result['role'],
            "bio": result['bio'],
            "location": result['location'],
            "favoriteCategories": favorite_categories
        }
    except Exception as e:
        print(f"Session validation error: {e}")
        return None
    finally:
        conn.close()

def logout_user(token: str) -> bool:
    """Invalidate user session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get user_id before deleting
        cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
        session = cursor.fetchone()
        
        if session:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        
        return True
    except:
        return False
    finally:
        conn.close()


def get_or_create_google_user(email: str, name: str = None, avatar: str = None,
                               ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
    """
    Get or create a user from Google OAuth login.
    If user exists by email, log them in.
    If not, create new user and log them in.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if user exists by email
        cursor.execute('''
            SELECT id, username, email, name, avatar, role, bio, location, 
                   favorite_categories, is_active, created_at
            FROM users WHERE email = ?
        ''', (email,))
        
        user = cursor.fetchone()
        
        if user:
            # User exists
            if not user['is_active']:
                return {"success": False, "error": "Akun telah dinonaktifkan"}
            
            user_id = user['id']
            
            # Update name/avatar if provided and different
            updates = []
            values = []
            if name and name != user['name']:
                updates.append("name = ?")
                values.append(name)
            if avatar and avatar != user['avatar']:
                updates.append("avatar = ?")
                values.append(avatar)
            
            if updates:
                values.append(user_id)
                cursor.execute(f'''
                    UPDATE users SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', values)
                conn.commit()
        else:
            # Create new user
            # Generate username from email (before @)
            base_username = email.split('@')[0]
            username = base_username
            suffix = 1
            
            # Ensure unique username
            while True:
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if not cursor.fetchone():
                    break
                username = f"{base_username}{suffix}"
                suffix += 1
            
            # Create random password (user won't use it, they login via Google)
            random_password = secrets.token_urlsafe(32)
            password_hash = hash_password(random_password)
            
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, name, avatar, role)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, password_hash, name or username, avatar or '😊', 'user'))
            
            user_id = cursor.lastrowid
            conn.commit()
        
        # Create session token
        token = generate_session_token()
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute('''
            INSERT INTO sessions (user_id, token, expires_at, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, token, expires_at, ip_address, user_agent))
        
        # Update last login
        cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user_id,))
        conn.commit()
        
        # Fetch updated user data
        cursor.execute('''
            SELECT id, username, email, name, avatar, role, bio, location, 
                   favorite_categories, created_at
            FROM users WHERE id = ?
        ''', (user_id,))
        
        u = cursor.fetchone()
        
        favorite_categories = []
        try:
            favorite_categories = json.loads(u['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": u['id'],
                "username": u['username'],
                "email": u['email'],
                "name": u['name'],
                "avatar": u['avatar'],
                "role": u['role'],
                "bio": u['bio'],
                "location": u['location'],
                "favoriteCategories": favorite_categories,
                "createdAt": u['created_at']
            }
        }
    except Exception as e:
        print(f"Google OAuth error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def update_user(user_id: int, **kwargs) -> Dict[str, Any]:
    """Update user profile"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    allowed_fields = ['name', 'avatar', 'bio', 'location', 'favorite_categories']
    update_fields = []
    values = []
    
    for field in allowed_fields:
        if field in kwargs:
            value = kwargs[field]
            if field == 'favorite_categories' and isinstance(value, list):
                value = json.dumps(value)
            update_fields.append(f"{field} = ?")
            values.append(value)
    
    if not update_fields:
        return {"success": False, "error": "No fields to update"}
    
    values.append(user_id)
    
    try:
        cursor.execute(f'''
            UPDATE users SET {", ".join(update_fields)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        conn.commit()
        
        return {"success": True, "message": "Profile updated successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def change_password(user_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
    """Change user password"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "error": "User not found"}
        
        if not verify_password(old_password, user['password_hash']):
            return {"success": False, "error": "Password lama salah"}
        
        new_hash = hash_password(new_password)
        cursor.execute('''
            UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (new_hash, user_id))
        
        # Invalidate all sessions except current
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        
        conn.commit()
        
        return {"success": True, "message": "Password berhasil diubah"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, username, email, name, avatar, role, bio, location, 
                   favorite_categories, created_at, last_login, is_active
            FROM users WHERE id = ?
        ''', (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return None
        
        favorite_categories = []
        try:
            favorite_categories = json.loads(user['favorite_categories'] or '[]')
        except:
            pass
        
        return {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "name": user['name'],
            "avatar": user['avatar'],
            "role": user['role'],
            "bio": user['bio'],
            "location": user['location'],
            "favoriteCategories": favorite_categories,
            "createdAt": user['created_at'],
            "lastLogin": user['last_login'],
            "isActive": bool(user['is_active'])
        }
    except:
        return None
    finally:
        conn.close()

def get_all_users(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Get all users (admin function)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        query = '''
            SELECT u.id, u.username, u.email, u.name, u.avatar, u.role, u.bio, u.location,
                   u.created_at, u.last_login, u.is_active,
                   COUNT(ch.id) AS chat_count,
                   MAX(ch.created_at) AS last_chat_at
            FROM users u
            LEFT JOIN chat_history ch ON ch.user_id = u.id
        '''
        if not include_inactive:
            query += " WHERE u.is_active = 1"
        query += " GROUP BY u.id ORDER BY u.created_at DESC"
        
        cursor.execute(query)
        users = cursor.fetchall()
        
        return [
            {
                "id": u['id'],
                "username": u['username'],
                "email": u['email'],
                "name": u['name'],
                "avatar": u['avatar'],
                "role": u['role'],
                "bio": u['bio'],
                "location": u['location'],
                "createdAt": u['created_at'],
                "lastLogin": u['last_login'],
                "chatCount": u['chat_count'] or 0,
                "lastActive": u['last_chat_at'] or u['last_login'],
                "isActive": bool(u['is_active'])
            }
            for u in users
        ]
    except:
        return []
    finally:
        conn.close()

def delete_user(user_id: int, admin_id: int) -> Dict[str, Any]:
    """Delete (deactivate) user account"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if trying to delete self as admin
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return {"success": False, "error": "User not found"}
        
        # Soft delete - just deactivate
        cursor.execute('''
            UPDATE users SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (user_id,))
        
        # Delete all sessions
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        
        conn.commit()
        
        return {"success": True, "message": "User account deactivated"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

# ============================================
# Chat History Functions
# ============================================

def save_chat(user_id: Optional[int], session_id: str, question: str, answer: str,
              category: str = None, response_time_ms: int = None, 
              model_used: str = None, conversation_id: str = None) -> int:
    """Save chat to history"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO chat_history 
            (user_id, session_id, conversation_id, question, answer, category, response_time_ms, model_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, session_id, conversation_id, question, answer, category, response_time_ms, model_used))
        chat_id = cursor.lastrowid

        # Keep conversations.message_count in sync
        if conversation_id:
            cursor.execute(
                'UPDATE conversations SET message_count = message_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (conversation_id,)
            )

        conn.commit()
        return chat_id
    except:
        return -1
    finally:
        conn.close()

def get_user_chat_history(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get chat history for a user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, question, answer, category, response_time_ms, model_used, created_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit))
        
        chats = cursor.fetchall()
        
        return [
            {
                "id": c['id'],
                "question": c['question'],
                "answer": c['answer'],
                "category": c['category'],
                "responseTime": c['response_time_ms'],
                "modelUsed": c['model_used'],
                "timestamp": c['created_at']
            }
            for c in chats
        ]
    except:
        return []
    finally:
        conn.close()

def get_session_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Get chat history for a session (for guests)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT id, question, answer, category, created_at
            FROM chat_history
            WHERE session_id = ?
            ORDER BY created_at ASC
        ''', (session_id,))
        
        return [dict(c) for c in cursor.fetchall()]
    except:
        return []
    finally:
        conn.close()


# ============================================
# Conversation Management Functions
# ============================================

def upsert_conversation(conversation_id: str, user_id: Optional[int], title: str = 'General') -> bool:
    """Create or update a conversation thread record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO conversations (id, user_id, title, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                updated_at = CURRENT_TIMESTAMP
        ''', (conversation_id, user_id, title))
        conn.commit()
        return True
    except Exception as e:
        print(f"upsert_conversation error: {e}")
        return False
    finally:
        conn.close()


def get_conversation_context(conversation_id: str, limit: int = 8) -> List[Dict[str, str]]:
    """Return the last `limit` Q&A turns for a conversation as [{role, content}] pairs.

    This list is passed directly to the LLM as conversation history so it can
    understand the full thread context when answering follow-up questions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # DESC to get the LAST `limit` turns (most recent), then reverse for chronological order
        cursor.execute('''
            SELECT question, answer
            FROM chat_history
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (conversation_id, limit))
        rows = cursor.fetchall()
        rows = list(reversed(rows))  # restore chronological order
        history = []
        for row in rows:
            history.append({"role": "user", "content": row["question"]})
            history.append({"role": "assistant", "content": row["answer"]})
        return history
    except Exception as e:
        print(f"get_conversation_context error: {e}")
        return []
    finally:
        conn.close()


def get_user_conversations(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Return conversation list for a user (for sidebar sync)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT c.id, c.title, c.message_count, c.created_at, c.updated_at,
                   COUNT(ch.id) AS actual_count
            FROM conversations c
            LEFT JOIN chat_history ch ON ch.conversation_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "message_count": r["actual_count"],
                "createdAt": r["created_at"],
                "updatedAt": r["updated_at"],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"get_user_conversations error: {e}")
        return []
    finally:
        conn.close()


def delete_conversation(conversation_id: str, user_id: int) -> bool:
    """Delete a single conversation and its chat history for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Only delete if it belongs to this user
        cursor.execute('DELETE FROM chat_history WHERE conversation_id = ? AND user_id = ?',
                       (conversation_id, user_id))
        cursor.execute('DELETE FROM conversations WHERE id = ? AND user_id = ?',
                       (conversation_id, user_id))
        conn.commit()
        return cursor.rowcount >= 0
    except Exception as e:
        print(f"delete_conversation error: {e}")
        return False
    finally:
        conn.close()


def clear_user_conversations(user_id: int) -> int:
    """Delete ALL conversations and chat history for a user. Returns count deleted."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
        chat_deleted = cursor.rowcount
        cursor.execute('DELETE FROM conversations WHERE user_id = ?', (user_id,))
        conv_deleted = cursor.rowcount
        conn.commit()
        return conv_deleted
    except Exception as e:
        print(f"clear_user_conversations error: {e}")
        return 0
    finally:
        conn.close()


# ============================================
# System Stats Functions
# ============================================

def get_system_stats() -> Dict[str, Any]:
    """Get system statistics (admin function)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Total users
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1")
        total_users = cursor.fetchone()['count']
        
        # Users by role
        cursor.execute('''
            SELECT role, COUNT(*) as count FROM users 
            WHERE is_active = 1 GROUP BY role
        ''')
        users_by_role = {r['role']: r['count'] for r in cursor.fetchall()}
        
        # Total chats
        cursor.execute("SELECT COUNT(*) as count FROM chat_history")
        total_chats = cursor.fetchone()['count']
        
        # Chats today
        cursor.execute('''
            SELECT COUNT(*) as count FROM chat_history 
            WHERE DATE(created_at) = DATE('now')
        ''')
        chats_today = cursor.fetchone()['count']
        
        # Active sessions
        cursor.execute('''
            SELECT COUNT(*) as count FROM sessions 
            WHERE expires_at > CURRENT_TIMESTAMP
        ''')
        active_sessions = cursor.fetchone()['count']
        
        # Recent registrations (last 7 days)
        cursor.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE created_at > datetime('now', '-7 days')
        ''')
        recent_registrations = cursor.fetchone()['count']
        
        return {
            "totalUsers": total_users,
            "usersByRole": users_by_role,
            "totalChats": total_chats,
            "chatsToday": chats_today,
            "activeSessions": active_sessions,
            "recentRegistrations": recent_registrations
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

# ============================================
# Feedback Functions
# ============================================

def save_feedback(user_id: Optional[int], chat_id: int, rating: int, 
                 comment: str = None, message_hash: str = None) -> dict:
    """Save or toggle feedback for a chat response.
    
    Toggle logic (like ChatGPT):
    - If user already gave same rating → remove it (set 0)
    - If user gave different rating → switch to new rating
    - If no existing feedback → insert new
    
    Returns dict with {rating, toggled, action}
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        final_rating = rating
        action = "created"
        
        # Check for existing feedback from this user for this message
        if user_id and message_hash:
            cursor.execute('''
                SELECT id, rating FROM feedback 
                WHERE user_id = ? AND message_hash = ?
            ''', (user_id, message_hash))
            existing = cursor.fetchone()
            
            if existing:
                old_rating = existing['rating']
                if old_rating == rating:
                    # Toggle off — same button clicked again
                    final_rating = 0
                    action = "toggled_off"
                else:
                    # Switch rating
                    action = "switched"
                
                cursor.execute('''
                    UPDATE feedback SET rating = ?, created_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (final_rating, existing['id']))
                conn.commit()
                return {"rating": final_rating, "toggled": True, "action": action}
        
        # No existing → insert new
        cursor.execute('''
            INSERT INTO feedback (user_id, chat_id, rating, comment, message_hash)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, chat_id, final_rating, comment, message_hash))
        conn.commit()
        return {"rating": final_rating, "toggled": False, "action": action}
    except Exception as e:
        print(f"❌ save_feedback error: {e}")
        return {"rating": rating, "toggled": False, "action": "error"}
    finally:
        conn.close()


def get_feedback_stats() -> Dict[str, Any]:
    """Get feedback statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT AVG(rating) as avg, COUNT(*) as count FROM feedback")
        result = cursor.fetchone()
        
        cursor.execute('''
            SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating ORDER BY rating
        ''')
        distribution = {r['rating']: r['count'] for r in cursor.fetchall()}
        
        return {
            "averageRating": round(result['avg'] or 0, 2),
            "totalFeedback": result['count'],
            "distribution": distribution
        }
    except:
        return {"averageRating": 0, "totalFeedback": 0, "distribution": {}}
    finally:
        conn.close()

def get_analytics_data(limit_recent: int = 50) -> Dict[str, Any]:
    """Get comprehensive CAG vs RAG research analytics"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # --- CAG vs RAG latency comparison ---
        cursor.execute('''
            SELECT category,
                   AVG(response_time_ms) as avg_ms,
                   MIN(response_time_ms) as min_ms,
                   MAX(response_time_ms) as max_ms,
                   COUNT(*) as count
            FROM chat_history
            WHERE category IN ('cag_cache', 'rag') AND response_time_ms IS NOT NULL
            GROUP BY category
        ''')
        latency = {}
        for row in cursor.fetchall():
            latency[row['category']] = {
                "avg_ms": round(row['avg_ms'] or 0, 1),
                "min_ms": row['min_ms'] or 0,
                "max_ms": row['max_ms'] or 0,
                "count": row['count']
            }

        # --- Overall traffic counts ---
        cursor.execute("SELECT COUNT(*) as total FROM chat_history")
        total = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) as count FROM chat_history WHERE category = 'cag_cache'")
        cag_hits = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM chat_history WHERE category = 'rag'")
        rag_hits = cursor.fetchone()['count']

        hit_rate_pct = round((cag_hits / total * 100) if total > 0 else 0, 1)

        # --- Daily hit-rate trend (last 30 days) ---
        cursor.execute('''
            SELECT DATE(created_at) as day,
                   SUM(CASE WHEN category='cag_cache' THEN 1 ELSE 0 END) as cache_hits,
                   COUNT(*) as total
            FROM chat_history
            WHERE created_at > datetime('now', '-30 days')
            GROUP BY DATE(created_at)
            ORDER BY day ASC
        ''')
        daily = [
            {
                "date": row['day'],
                "hits": row['cache_hits'],
                "total": row['total'],
                "rate": round((row['cache_hits'] / row['total'] * 100) if row['total'] > 0 else 0, 1)
            }
            for row in cursor.fetchall()
        ]

        # --- Accuracy from feedback (overall) ---
        cursor.execute('''
            SELECT
                SUM(CASE WHEN rating > 0 THEN 1 ELSE 0 END) as likes,
                SUM(CASE WHEN rating < 0 THEN 1 ELSE 0 END) as dislikes,
                COUNT(*) as total
            FROM feedback
        ''')
        fb = cursor.fetchone()
        likes = fb['likes'] or 0
        dislikes = fb['dislikes'] or 0
        total_feedback = fb['total'] or 0
        like_rate_pct = round((likes / total_feedback * 100) if total_feedback > 0 else 0, 1)

        # --- Accuracy broken down by source ---
        cursor.execute('''
            SELECT ch.category,
                   SUM(CASE WHEN f.rating > 0 THEN 1 ELSE 0 END) as likes,
                   SUM(CASE WHEN f.rating < 0 THEN 1 ELSE 0 END) as dislikes,
                   COUNT(f.id) as total
            FROM feedback f
            JOIN chat_history ch ON f.chat_id = ch.id
            WHERE ch.category IN ('cag_cache', 'rag')
            GROUP BY ch.category
        ''')
        fb_by_source = {}
        for row in cursor.fetchall():
            t = row['total'] or 0
            l = row['likes'] or 0
            fb_by_source[row['category']] = {
                "likes": l,
                "dislikes": row['dislikes'] or 0,
                "total": t,
                "like_rate_pct": round((l / t * 100) if t > 0 else 0, 1)
            }

        # --- Recent per-query table ---
        cursor.execute('''
            SELECT ch.id,
                   ch.question,
                   ch.answer,
                   ch.category,
                   ch.response_time_ms,
                   ch.created_at,
                   COALESCE(u.name, u.username, 'Guest') AS asked_by,
                   lf.rating
            FROM chat_history ch
            LEFT JOIN users u ON u.id = ch.user_id
            LEFT JOIN (
                SELECT f.chat_id, f.rating
                FROM feedback f
                INNER JOIN (
                    SELECT chat_id, MAX(id) AS max_id
                    FROM feedback
                    GROUP BY chat_id
                ) latest ON latest.max_id = f.id
            ) lf ON lf.chat_id = ch.id
            ORDER BY ch.created_at DESC
            LIMIT ?
        ''', (limit_recent,))
        recent_queries = [
            {
                "id": row['id'],
                "question": (row['question'] or "")[:120],
                "answer": (row['answer'] or "")[:220],
                "asked_by": row['asked_by'] or 'Guest',
                "source": row['category'],
                "response_time_ms": row['response_time_ms'],
                "rating": row['rating'],
                "created_at": row['created_at']
            }
            for row in cursor.fetchall()
        ]

        return {
            "latency": latency,
            "hit_rate": {
                "total": total,
                "cag_hits": cag_hits,
                "rag_hits": rag_hits,
                "hit_rate_pct": hit_rate_pct,
                "daily": daily
            },
            "accuracy": {
                "total_feedback": total_feedback,
                "likes": likes,
                "dislikes": dislikes,
                "like_rate_pct": like_rate_pct,
                "by_source": fb_by_source
            },
            "recent_queries": recent_queries
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

# ============================================
# Cleanup Functions
# ============================================

def cleanup_expired_sessions():
    """Remove expired sessions"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM sessions WHERE expires_at < CURRENT_TIMESTAMP")
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    except:
        return 0
    finally:
        conn.close()

# Initialize database when module is imported
if __name__ == "__main__":
    init_database()
    print("Database setup complete!")
    
    # Show stats
    stats = get_system_stats()
    print(f"\nSystem Stats:")
    print(f"  Total Users: {stats.get('totalUsers', 0)}")
    print(f"  Total Chats: {stats.get('totalChats', 0)}")
