// SafeMoney SPA Client Application Logic - Samsung One UI Desktop Style Overhaul

const STATE = {
  token: localStorage.getItem("safemoney_token") || null,
  username: localStorage.getItem("safemoney_username") || null,
  role: localStorage.getItem("safemoney_role") || null,
  user: null,
  currentView: "dashboard",
  transactions: [],
  goals: [],
  budgets: [],
  gamification: null,
  adminStats: null,
  adminUsers: [],
  adminLogs: [],
  adminDb: null,
  activeCharts: {},
  // One UI state elements
  theme: localStorage.getItem("safemoney_theme") || "system",
  sidebarCollapsed: localStorage.getItem("safemoney_sidebar_collapsed") === "true",
  searchQuery: ""
};

const CATEGORIES = [
  "Food", "Groceries", "Shopping", "Transportation", "Fuel", 
  "Medical expenses", "Education", "Entertainment", "Rent", 
  "Utility bills", "Internet bills", "Investments", 
  "Subscriptions", "Insurance", "Miscellaneous expenses"
];

// =================== THEME MANAGEMENT ===================
function getSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme() {
  let activeTheme = STATE.theme;
  if (activeTheme === "system") {
    activeTheme = getSystemTheme();
  }
  document.documentElement.setAttribute("data-theme", activeTheme);
}

function cycleTheme() {
  if (STATE.theme === "system") {
    STATE.theme = "light";
  } else if (STATE.theme === "light") {
    STATE.theme = "dark";
  } else {
    STATE.theme = "system";
  }
  localStorage.setItem("safemoney_theme", STATE.theme);
  applyTheme();
  
  // Re-render to update the theme icon and any charts
  render();
  showToast(`Theme preference set to: ${STATE.theme.toUpperCase()}`);
}

// Watch for system theme changes dynamically
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (STATE.theme === "system") {
    applyTheme();
  }
});

// Initialize theme on script run
applyTheme();


// =================== API HELPERS ===================
async function apiRequest(endpoint, method = "GET", body = null) {
  const headers = {};
  if (STATE.token) {
    headers["Authorization"] = `Bearer ${STATE.token}`;
  }
  if (body) {
    headers["Content-Type"] = "application/json";
  }

  const options = {
    method,
    headers,
    body: body ? JSON.stringify(body) : null
  };

  try {
    const response = await fetch(endpoint, options);
    if (response.status === 401) {
      logout();
      showToast("Session expired. Please log in again.", "error");
      throw new Error("Unauthorized");
    }
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || "API Request Failed");
    }
    return await response.json();
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
}

// Premium One UI Toast notification builder
function showToast(message, type = "success") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.style.cssText = "position: fixed; top: 24px; right: 24px; z-index: 10000; display: flex; flex-direction: column; gap: 12px; pointer-events: none;";
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement("div");
  toast.style.cssText = `
    padding: 14px 20px;
    border-radius: 16px;
    font-size: 14px;
    font-weight: 600;
    box-shadow: var(--card-shadow);
    min-width: 280px;
    max-width: 400px;
    border: 1px solid var(--card-border);
    border-left: 5px solid ${type === 'success' ? 'var(--income)' : 'var(--expense)'};
    background: var(--bg-secondary);
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 12px;
    pointer-events: auto;
    transform: translateY(-20px);
    opacity: 0;
    transition: transform 0.25s cubic-bezier(0.2, 0, 0, 1), opacity 0.25s cubic-bezier(0.2, 0, 0, 1);
  `;
  
  toast.innerHTML = `
    <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}" style="color: ${type === 'success' ? 'var(--income)' : 'var(--expense)'}; font-size: 16px;"></i>
    <span style="flex: 1;">${message}</span>
    <button style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:12px;" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>
  `;
  
  toastContainer.appendChild(toast);
  
  // Trigger entry animation
  requestAnimationFrame(() => {
    toast.style.transform = "translateY(0)";
    toast.style.opacity = "1";
  });

  setTimeout(() => {
    toast.style.transform = "translateY(-10px)";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}


// =================== AUTHENTICATION ===================
function saveSession(token, username, role) {
  STATE.token = token;
  STATE.username = username;
  STATE.role = role;
  localStorage.setItem("safemoney_token", token);
  localStorage.setItem("safemoney_username", username);
  localStorage.setItem("safemoney_role", role);
}

function logout() {
  STATE.token = null;
  STATE.username = null;
  STATE.role = null;
  STATE.user = null;
  localStorage.removeItem("safemoney_token");
  localStorage.removeItem("safemoney_username");
  localStorage.removeItem("safemoney_role");
  render();
}

function setView(view) {
  console.log("[DEBUG] setView called with:", view);
  STATE.currentView = view;
  
  // Cleanup active charts
  Object.keys(STATE.activeCharts).forEach(key => {
    if (STATE.activeCharts[key]) {
      STATE.activeCharts[key].destroy();
      delete STATE.activeCharts[key];
    }
  });
  
  render();
}


// =================== DATA SYNC ===================
async function loadUserData() {
  if (!STATE.token) return;
  try {
    STATE.user = await apiRequest("/api/profile");
    if (STATE.user.monthly_income === 0) {
      if (STATE.currentView !== "setup") {
        setView("setup");
      }
    }
  } catch (err) {
    console.error("loadUserData error:", err);
    logout();
  }
}

async function loadDashboardData() {
  if (!STATE.token) return;
  try {
    await loadUserData();
    if (STATE.currentView === "setup") return;
    
    STATE.transactions = await apiRequest("/api/transactions");
    STATE.goals = await apiRequest("/api/goals");
    
    const now = new Date();
    STATE.budgets = await apiRequest(`/api/budgets?month=${now.getMonth() + 1}&year=${now.getFullYear()}`);
    STATE.gamification = await apiRequest("/api/gamification/status");
  } catch (err) {
    console.error("loadDashboardData error:", err);
    showToast("Failed to sync dashboard metrics", "error");
  }
}

async function loadAdminData() {
  try {
    STATE.adminStats = await apiRequest("/api/admin/stats");
    STATE.adminUsers = await apiRequest("/api/admin/users");
    STATE.adminLogs = await apiRequest("/api/admin/logs");
    STATE.adminDb = await apiRequest("/api/admin/database");
  } catch (err) {
    showToast("Failed to fetch administrator statistics", "error");
  }
}


// =================== APPLICATION ROUTER / SHELL RENDER ===================
function render() {
  const root = document.getElementById("app-root");
  
  // Apply visual theme before rendering
  applyTheme();
  
  if (!STATE.token) {
    renderAuth(root);
  } else if (STATE.currentView === "setup") {
    renderSetup(root);
  } else {
    renderMainApp(root);
  }
}

// 1. Render Auth Pages (Samsung One UI Aesthetic Card)
function renderAuth(root) {
  const isRegister = STATE.authMode === "register";
  
  root.innerHTML = `
    <div class="auth-wrapper">
      <div class="auth-card">
        <div class="auth-header">
          <div class="auth-logo">
            <div class="logo-icon"><i class="fas fa-vault"></i></div>
            <span style="font-family: var(--font-heading); font-size: 24px; font-weight: 800; color: var(--text-primary);">SafeMoney</span>
          </div>
          <h2 style="font-size: 20px; font-weight: 700; color: var(--text-primary); margin-top: 8px;">
            ${isRegister ? "Create Account" : "Welcome Back"}
          </h2>
          <p style="color: var(--text-secondary); font-size: 13px; margin-top: 4px;">
            ${isRegister ? "Join SafeMoney to optimize your budgets and goals" : "Manage your daily budgets & AI analytics"}
          </p>
        </div>
        
        <form id="auth-form">
          ${isRegister ? `
            <div class="form-group">
              <label class="form-label">Email Address</label>
              <input type="email" id="auth-email" class="form-control" placeholder="name@domain.com" required>
            </div>
          ` : ""}
          <div class="form-group">
            <label class="form-label">Username</label>
            <input type="text" id="auth-username" class="form-control" placeholder="Enter username" required>
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" id="auth-password" class="form-control" placeholder="••••••••" required>
          </div>
          
          <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 12px; padding: 12px 20px;">
            ${isRegister ? "Register" : "Login"}
          </button>
        </form>

        ${!isRegister ? `
          <div style="text-align: center; margin: 14px 0 8px; color: var(--text-secondary); font-size: 12px;">or</div>
        ` : ""}
        
        <div style="text-align: center; margin-top: 20px; font-size: 13px; color: var(--text-secondary);">
          ${isRegister ? `
            Already have an account? <a href="#" id="auth-toggle" style="color: var(--primary); font-weight: 600;">Log In</a>
          ` : `
            New to SafeMoney? <a href="#" id="auth-toggle" style="color: var(--primary); font-weight: 600;">Create Account</a>
          `}
        </div>
      </div>
    </div>
  `;

  document.getElementById("auth-toggle").addEventListener("click", (e) => {
    e.preventDefault();
    STATE.authMode = isRegister ? "login" : "register";
    render();
  });

  document.getElementById("auth-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("auth-username").value;
    const password = document.getElementById("auth-password").value;
    
    try {
      if (isRegister) {
        const email = document.getElementById("auth-email").value;
        const res = await fetch("/auth/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, email, password })
        });
        if (!res.ok) {
          const err = await res.json();
          let errDetail = err.detail || "Registration failed";
          if (Array.isArray(err.detail)) {
            errDetail = err.detail[0].msg;
          }
          throw new Error(errDetail);
        }
        showToast("Registration successful! Please log in.");
        STATE.authMode = "login";
        render();
      } else {
        const formData = new URLSearchParams();
        formData.append("username", username);
        formData.append("password", password);
        const res = await fetch("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: formData
        });
        if (!res.ok) {
          const err = await res.json();
          let errDetail = err.detail || "Authentication failed";
          if (Array.isArray(err.detail)) {
            errDetail = err.detail[0].msg;
          }
          throw new Error(errDetail);
        }
        const data = await res.json();
        saveSession(data.access_token, data.username, data.role);
        showToast(`Welcome back, ${data.username}!`);
        await loadUserData();
        if (STATE.currentView !== "setup") {
          setView("dashboard");
        }
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 2. Render Setup view (Samsung One UI Setup wizard layout)
function renderSetup(root) {
  root.innerHTML = `
    <div class="auth-wrapper" style="max-width: 100%;">
      <div class="setup-card">
        <div style="text-align: center; margin-bottom: 28px;">
          <h2 style="font-family: var(--font-heading); font-size: 24px; color: var(--text-primary);">Setup Financial Profile</h2>
          <p style="color: var(--text-secondary); font-size: 13px; margin-top: 6px;">
            Set your current balance, monthly income, and initial goals to enable smart budget carry-forward algorithms.
          </p>
        </div>
        
        <form id="setup-form">
          <div class="grid-cols-2" style="margin-bottom: 20px;">
            <div class="form-group" style="margin-bottom: 0;">
              <label class="form-label">Current Balance (₹)</label>
              <input type="number" id="setup-balance" class="form-control" placeholder="e.g. 25000" min="0" required>
            </div>
            <div class="form-group" style="margin-bottom: 0;">
              <label class="form-label">Monthly Income (₹)</label>
              <input type="number" id="setup-income" class="form-control" placeholder="e.g. 50000" min="0" required>
            </div>
          </div>
          
          <div class="grid-cols-2" style="margin-bottom: 20px;">
            <div class="form-group" style="margin-bottom: 0;">
              <label class="form-label">Recurring Monthly Expenses (₹)</label>
              <input type="number" id="setup-recurring" class="form-control" placeholder="e.g. 15000" min="0" value="0">
            </div>
            <div class="form-group" style="margin-bottom: 0;">
              <label class="form-label">Monthly Reserved Amount (₹)</label>
              <input type="number" id="setup-reserved" class="form-control" placeholder="e.g. 5000" min="0" value="0">
            </div>
          </div>
          
          <h3 style="font-size: 16px; margin: 24px 0 12px 0; font-family: var(--font-heading); color: var(--text-primary); display: flex; align-items: center; gap: 8px;">
            <i class="fas fa-bullseye" style="color: var(--primary);"></i> Configure Savings Objectives
          </h3>
          
          <div id="goals-list-container" style="display: flex; flex-direction: column; gap: 14px; margin-bottom: 24px;">
            <div class="goal-entry-row">
              <div class="grid-cols-2" style="margin-bottom: 12px;">
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Goal Title</label>
                  <input type="text" class="form-control goal-title" placeholder="e.g. Purchase Laptop" required>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Goal Category / Purpose</label>
                  <select class="form-control goal-purpose">
                    <option value="Laptop">Purchase Laptop</option>
                    <option value="Education">Funding Higher Education</option>
                    <option value="Vehicle">Buying a Vehicle</option>
                    <option value="Vacation">Planning a Vacation</option>
                    <option value="Investment">Making Investments</option>
                    <option value="Home">Purchasing a Home</option>
                    <option value="Other">Other Objective</option>
                  </select>
                </div>
              </div>
              <div class="grid-cols-3" style="margin-bottom: 0;">
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Target Amount (₹)</label>
                  <input type="number" class="form-control goal-target" placeholder="e.g. 60000" min="1" required>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Completion Target Date</label>
                  <input type="date" class="form-control goal-date" required>
                </div>
                <div class="form-group" style="margin-bottom: 0;">
                  <label class="form-label">Monthly Target Contribution (₹)</label>
                  <input type="number" class="form-control goal-contribution" placeholder="e.g. 5000" min="0" required>
                </div>
              </div>
            </div>
          </div>
          
          <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 24px;">
            <button type="button" class="btn" id="btn-add-goal-row">
              <i class="fas fa-plus"></i> Add Goal Row
            </button>
            <button type="submit" class="btn btn-primary" style="padding: 10px 24px;">
              Complete Setup <i class="fas fa-arrow-right" style="margin-left: 6px;"></i>
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  // Set default goal date to 6 months from now
  const defaultDate = new Date();
  defaultDate.setMonth(defaultDate.getMonth() + 6);
  document.querySelector(".goal-date").value = defaultDate.toISOString().split('T')[0];

  document.getElementById("btn-add-goal-row").addEventListener("click", () => {
    const container = document.getElementById("goals-list-container");
    const newRow = document.createElement("div");
    newRow.className = "goal-entry-row";
    newRow.style.position = "relative";
    newRow.innerHTML = `
      <button type="button" class="btn-remove-goal-row" style="position: absolute; right: 12px; top: 12px; background: none; border: none; color: var(--expense); cursor: pointer; font-size: 14px;"><i class="fas fa-times"></i></button>
      <div class="grid-cols-2" style="margin-bottom: 12px;">
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Goal Title</label>
          <input type="text" class="form-control goal-title" placeholder="e.g. Vacation Fund" required>
        </div>
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Goal Category / Purpose</label>
          <select class="form-control goal-purpose">
            <option value="Laptop">Purchase Laptop</option>
            <option value="Education">Funding Higher Education</option>
            <option value="Vehicle">Buying a Vehicle</option>
            <option value="Vacation">Planning a Vacation</option>
            <option value="Investment">Making Investments</option>
            <option value="Home">Purchasing a Home</option>
            <option value="Other">Other Objective</option>
          </select>
        </div>
      </div>
      <div class="grid-cols-3" style="margin-bottom: 0;">
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Target Amount (₹)</label>
          <input type="number" class="form-control goal-target" placeholder="e.g. 20000" min="1" required>
        </div>
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Completion Target Date</label>
          <input type="date" class="form-control goal-date" required>
        </div>
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Monthly Target Contribution (₹)</label>
          <input type="number" class="form-control goal-contribution" placeholder="e.g. 2000" min="0" required>
        </div>
      </div>
    `;
    
    const futureDate = new Date();
    futureDate.setMonth(futureDate.getMonth() + 6);
    newRow.querySelector(".goal-date").value = futureDate.toISOString().split('T')[0];
    newRow.querySelector(".btn-remove-goal-row").addEventListener("click", () => newRow.remove());
    container.appendChild(newRow);
  });

  document.getElementById("setup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const balance = parseFloat(document.getElementById("setup-balance").value);
    const income = parseFloat(document.getElementById("setup-income").value);
    const recurring = parseFloat(document.getElementById("setup-recurring").value) || 0.0;
    const reserved = parseFloat(document.getElementById("setup-reserved").value) || 0.0;
    
    const goalRows = document.querySelectorAll(".goal-entry-row");
    const goals = [];
    goalRows.forEach(row => {
      goals.push({
        title: row.querySelector(".goal-title").value,
        purpose: row.querySelector(".goal-purpose").value,
        target_amount: parseFloat(row.querySelector(".goal-target").value),
        target_date: row.querySelector(".goal-date").value,
        monthly_contribution: parseFloat(row.querySelector(".goal-contribution").value)
      });
    });

    try {
      await apiRequest("/api/setup", "POST", {
        current_balance: balance,
        monthly_income: income,
        recurring_expenses: recurring,
        reserved_amount: reserved,
        goals
      });
      showToast("Profile configured successfully! Bonus XP awarded.");
      setView("dashboard");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 3. Render Main App Shell Structure (Desktop layout with collapsible left sidebar)
function renderMainApp(root) {
  // Breadcrumb current view mapping name
  const viewsBreadcrumbs = {
    dashboard: "Dashboard",
    transactions: "Transactions Management",
    goals: "Savings Goals Portfolio",
    simulation: "What-If Simulator",
    gamification: "Rewards & Challenges",
    admin: "Governance Administration",
    settings: "System Preferences"
  };
  
  root.innerHTML = `
    <div class="app-container ${STATE.sidebarCollapsed ? 'sidebar-collapsed' : ''}">
      <!-- Sidebar Navigation Panel -->
      <aside class="sidebar ${STATE.sidebarCollapsed ? 'collapsed' : ''}">
        <div class="logo-container">
          <div class="logo-icon"><i class="fas fa-wallet"></i></div>
          <span class="logo-text">SafeMoney</span>
        </div>
        
        <ul class="nav-links">
          <li class="nav-item ${STATE.currentView === 'dashboard' ? 'active' : ''}" onclick="setView('dashboard')" title="Dashboard">
            <i class="fas fa-chart-line"></i> <span>Dashboard</span>
          </li>
          <li class="nav-item ${STATE.currentView === 'transactions' ? 'active' : ''}" onclick="setView('transactions')" title="Transactions">
            <i class="fas fa-exchange-alt"></i> <span>Transactions</span>
          </li>
          <li class="nav-item ${STATE.currentView === 'goals' ? 'active' : ''}" onclick="setView('goals')" title="Savings Goals">
            <i class="fas fa-bullseye"></i> <span>Savings Goals</span>
          </li>
          <li class="nav-item ${STATE.currentView === 'simulation' ? 'active' : ''}" onclick="setView('simulation')" title="What-If Simulation">
            <i class="fas fa-sliders-h"></i> <span>What-If Simulation</span>
          </li>
          <li class="nav-item ${STATE.currentView === 'gamification' ? 'active' : ''}" onclick="setView('gamification')" title="Rewards & Badges">
            <i class="fas fa-trophy"></i> <span>Rewards & Badges</span>
          </li>
          ${STATE.role === 'admin' ? `
            <li class="nav-item ${STATE.currentView === 'admin' ? 'active' : ''}" onclick="setView('admin')" title="Admin Panel">
              <i class="fas fa-user-shield"></i> <span>Admin Panel</span>
            </li>
          ` : ""}
          <li class="nav-item ${STATE.currentView === 'settings' ? 'active' : ''}" onclick="setView('settings')" title="Settings">
            <i class="fas fa-cog"></i> <span>Settings</span>
          </li>
          <li class="nav-item" onclick="logout()" style="color: var(--expense); margin-top: auto;" title="Logout">
            <i class="fas fa-sign-out-alt"></i> <span>Logout</span>
          </li>
        </ul>
        
        <div class="user-badge-widget" style="margin-top: 16px;">
          <div class="user-widget-profile">
            <div class="avatar">${STATE.username.substring(0,2).toUpperCase()}</div>
            <div>
              <div class="username-display">${STATE.username}</div>
              <div class="points-pill"><i class="fas fa-coins"></i> ${STATE.user ? STATE.user.points : 0} XP</div>
            </div>
          </div>
          <div class="widget-details">
            <span>Streak: <b>${STATE.user ? STATE.user.streak_days : 0} Days</b></span>
            <span>Health: <b>${STATE.user ? STATE.user.financial_health_score : 100}%</b></span>
          </div>
        </div>
      </aside>

      <!-- Main workspace content -->
      <main class="main-content">
        <header class="oneui-header">
          <div class="header-left">
            <button class="sidebar-toggle-btn" id="btn-toggle-sidebar" title="Toggle Sidebar">
              <i class="fas fa-bars"></i>
            </button>
            <div>
              <div class="breadcrumb-container">
                <span class="breadcrumb-item">SafeMoney</span>
                <i class="fas fa-chevron-right" style="font-size: 8px; margin: 0 4px;"></i>
                <span class="breadcrumb-item active">${viewsBreadcrumbs[STATE.currentView]}</span>
              </div>
              <h1 class="page-title">${viewsBreadcrumbs[STATE.currentView]}</h1>
            </div>
          </div>
          
          <div class="search-wrapper">
            <i class="fas fa-search search-icon"></i>
            <input type="text" id="global-search-input" class="search-input" placeholder="Search transactions, challenges..." value="${STATE.searchQuery}">
          </div>
          
          <div class="header-right">
            <button class="quick-action-btn" id="btn-theme-toggle" title="Toggle Theme">
              <i class="fas ${STATE.theme === 'dark' ? 'fa-sun' : STATE.theme === 'light' ? 'fa-moon' : 'fa-circle-half-stroke'}"></i>
            </button>
            <button class="quick-action-btn" id="btn-quick-expense-header" title="Quick Record Expense">
              <i class="fas fa-plus"></i>
            </button>
            <button class="quick-action-btn" id="btn-notifications" title="Notifications">
              <i class="fas fa-bell"></i>
              <span class="badge"></span>
            </button>
            
            <div style="position: relative;">
              <div class="avatar" id="avatar-menu-trigger" style="cursor: pointer;">
                ${STATE.username.substring(0,2).toUpperCase()}
              </div>
              <div class="dropdown-menu" id="user-dropdown-menu">
                <div style="padding: 12px 16px;">
                  <div style="font-weight: 700; color: var(--text-primary);">${STATE.username}</div>
                  <div style="font-size: 11px; color: var(--text-secondary);">${STATE.role === 'admin' ? 'Administrator' : 'Standard User'}</div>
                </div>
                <div class="dropdown-divider"></div>
                <div class="dropdown-item" id="menu-view-settings"><i class="fas fa-cog"></i> Settings</div>
                ${STATE.role === 'admin' ? `<div class="dropdown-item" id="menu-view-admin"><i class="fas fa-user-shield"></i> Admin Panel</div>` : ""}
                <div class="dropdown-divider"></div>
                <div class="dropdown-item" id="menu-logout" style="color: var(--expense);"><i class="fas fa-sign-out-alt"></i> Logout</div>
              </div>
            </div>
          </div>
        </header>
        
        <div id="main-content-mount">
          <div style="display: flex; justify-content: center; align-items: center; height: 50vh;">
            <i class="fas fa-circle-notch fa-spin" style="font-size: 30px; color: var(--primary);"></i>
          </div>
        </div>
      </main>
    </div>
  `;

  // Attach Shell Event Listeners
  document.getElementById("btn-toggle-sidebar").addEventListener("click", () => {
    STATE.sidebarCollapsed = !STATE.sidebarCollapsed;
    localStorage.setItem("safemoney_sidebar_collapsed", STATE.sidebarCollapsed);
    const container = document.querySelector(".app-container");
    const sidebar = document.querySelector(".sidebar");
    
    if (STATE.sidebarCollapsed) {
      container.classList.add("sidebar-collapsed");
      sidebar.classList.add("collapsed");
    } else {
      container.classList.remove("sidebar-collapsed");
      sidebar.classList.remove("collapsed");
    }
  });

  document.getElementById("btn-theme-toggle").addEventListener("click", () => {
    cycleTheme();
  });

  document.getElementById("btn-quick-expense-header").addEventListener("click", () => {
    showQuickExpenseModal();
  });

  document.getElementById("btn-notifications").addEventListener("click", () => {
    showToast("Notifications system connected. All systems functional!");
  });

  // Avatar Dropdown Menu trigger toggle
  const avatarTrigger = document.getElementById("avatar-menu-trigger");
  const userMenu = document.getElementById("user-dropdown-menu");
  avatarTrigger.addEventListener("click", (e) => {
    e.stopPropagation();
    userMenu.classList.toggle("active");
  });
  
  document.addEventListener("click", () => {
    if (userMenu) userMenu.classList.remove("active");
  });

  document.getElementById("menu-view-settings").addEventListener("click", () => setView("settings"));
  if (STATE.role === 'admin') {
    document.getElementById("menu-view-admin").addEventListener("click", () => setView("admin"));
  }
  document.getElementById("menu-logout").addEventListener("click", logout);

  // Search input events
  const searchInput = document.getElementById("global-search-input");
  searchInput.addEventListener("input", (e) => {
    STATE.searchQuery = e.target.value.toLowerCase().trim();
    // Filter currently loaded view content (dynamic client filtering)
    filterCurrentViewContent();
  });

  // Trigger loading and inner sub-view rendering
  loadAndRenderSubView();
}

// Dynamically filter active views content on keypress search
function filterCurrentViewContent() {
  const mount = document.getElementById("main-content-mount");
  if (!mount) return;
  
  if (STATE.currentView === "transactions") {
    // Dynamically filter table rows
    const rows = mount.querySelectorAll(".custom-table tbody tr");
    let hasVisibleRows = false;
    
    rows.forEach(row => {
      const text = row.innerText.toLowerCase();
      if (text.includes(STATE.searchQuery)) {
        row.style.display = "";
        hasVisibleRows = true;
      } else {
        row.style.display = "none";
      }
    });

    // Handle empty search feedback row
    let noMatchRow = mount.querySelector(".no-match-search-row");
    if (!hasVisibleRows && rows.length > 0 && !noMatchRow) {
      const tbody = mount.querySelector(".custom-table tbody");
      noMatchRow = document.createElement("tr");
      noMatchRow.className = "no-match-search-row";
      noMatchRow.innerHTML = `<td colspan="8" style="text-align:center; color: var(--text-muted); padding: 20px;">No transactions match your search filter.</td>`;
      tbody.appendChild(noMatchRow);
    } else if (hasVisibleRows && noMatchRow) {
      noMatchRow.remove();
    }
  } else if (STATE.currentView === "gamification") {
    // Filter active challenge cards
    const cards = mount.querySelectorAll(".challenges-feed-container .oneui-card");
    cards.forEach(card => {
      const text = card.innerText.toLowerCase();
      if (text.includes(STATE.searchQuery)) {
        card.style.display = "";
      } else {
        card.style.display = "none";
      }
    });
  }
}

async function loadAndRenderSubView() {
  const mount = document.getElementById("main-content-mount");
  if (!mount) return;

  if (STATE.currentView === "admin") {
    await loadAdminData();
    renderAdmin(mount);
  } else {
    await loadDashboardData();
    if (STATE.currentView === "dashboard") renderDashboard(mount);
    if (STATE.currentView === "transactions") renderTransactions(mount);
    if (STATE.currentView === "goals") renderGoals(mount);
    if (STATE.currentView === "simulation") renderSimulation(mount);
    if (STATE.currentView === "gamification") renderGamification(mount);
    if (STATE.currentView === "settings") renderSettings(mount);
  }
  
  // Re-apply filter matching if query exists
  if (STATE.searchQuery) {
    filterCurrentViewContent();
  }
}


// =================== VIEW SPECIFIC MODULES ===================

// 1. Dashboard Module Overhaul
function renderDashboard(mount) {
  // Compute key stats
  const todayStr = new Date().toISOString().split('T')[0];
  const todayBudgetObj = (STATE.budgets || []).find(b => b.date === todayStr);
  const remainingDaily = todayBudgetObj ? (todayBudgetObj.final_budget + todayBudgetObj.budget_boost - todayBudgetObj.spent_amount) : 0.0;
  
  const totalExpenses = (STATE.transactions || []).filter(t => t.type === 'expense').reduce((sum, t) => sum + t.amount, 0.0);
  const totalIncome = (STATE.transactions || []).filter(t => t.type === 'income').reduce((sum, t) => sum + t.amount, 0.0) || (STATE.user ? STATE.user.monthly_income : 0);
  const remainingMonthlyBudget = Math.max(0.0, totalIncome - totalExpenses);

  mount.innerHTML = `
    <!-- Top-level grid: Left (Wellness Metrics) & Right (AI suggestions and health ring) -->
    <div class="grid-cols-3-layout">
      <div>
        <!-- Rolling daily math box -->
        <div class="oneui-card" style="margin-bottom: 24px; background: linear-gradient(135deg, var(--primary-glow), rgba(0, 176, 116, 0.02)); border: 1px solid var(--primary-glow);">
          <div class="card-header" style="margin-bottom: 12px;">
            <div class="card-title"><i class="fas fa-gift" style="color: var(--income);"></i> Smart Budget Boost Summary</div>
            <span class="badge-pill" style="font-size: 11px; background: ${STATE.user.gift_budget_boost_enabled ? 'var(--income-glow)' : 'var(--expense-glow)'}; color: ${STATE.user.gift_budget_boost_enabled ? 'var(--income)' : 'var(--expense)'}; border: 1px solid currentColor;">
              ${STATE.user.gift_budget_boost_enabled ? 'Active Boost Enabled' : 'Boost Disabled'}
            </span>
          </div>
          
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 16px; text-align: center;">
            <div style="padding: 8px 0; border-right: 1px solid var(--card-border);">
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Base Daily Budget</div>
              <div style="font-size: 16px; font-weight: 700;">₹${(todayBudgetObj ? todayBudgetObj.final_budget : 0.0).toLocaleString('en-IN', {minimumFractionDigits:2})}</div>
            </div>
            <div style="padding: 8px 0; border-right: 1px solid var(--card-border);">
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Smart Income Boost</div>
              <div style="font-size: 16px; font-weight: 700; color: var(--income);">+₹${(todayBudgetObj ? todayBudgetObj.budget_boost : 0.0).toLocaleString('en-IN', {minimumFractionDigits:2})}</div>
            </div>
            <div style="padding: 8px 0; border-right: 1px solid var(--card-border);">
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Adjusted Daily Budget</div>
              <div style="font-size: 16px; font-weight: 800; color: var(--primary);">₹${(todayBudgetObj ? (todayBudgetObj.final_budget + todayBudgetObj.budget_boost) : 0.0).toLocaleString('en-IN', {minimumFractionDigits:2})}</div>
            </div>
            <div style="padding: 8px 0; border-right: 1px solid var(--card-border);">
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Remaining Allowance</div>
              <div style="font-size: 16px; font-weight: 700; color: ${remainingDaily < 0 ? 'var(--expense)' : 'var(--income)'}">₹${remainingDaily.toLocaleString('en-IN', {minimumFractionDigits:2})}</div>
            </div>
            <div style="padding: 8px 0;">
              <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 4px;">Current Bank Balance</div>
              <div style="font-size: 16px; font-weight: 700;">₹${STATE.user.current_balance.toLocaleString('en-IN', {minimumFractionDigits:2})}</div>
            </div>
          </div>
        </div>
        
        <!-- Large Metrics Stat Grid -->
        <div class="grid-cols-2" style="margin-bottom: 24px;">
          <div class="oneui-card stat-card blue">
            <div class="stat-card-accent-bar"></div>
            <span class="stat-label">Available Account Balance</span>
            <span class="stat-value">₹${STATE.user.current_balance.toLocaleString('en-IN', {minimumFractionDigits:2})}</span>
            <span class="stat-subtitle">Liquidity balance</span>
          </div>
          <div class="oneui-card stat-card emerald">
            <div class="stat-card-accent-bar"></div>
            <span class="stat-label">Today's Balance Budget</span>
            <span class="stat-value" style="color: ${remainingDaily < 0 ? 'var(--expense)' : 'var(--income)'}">
              ₹${remainingDaily.toLocaleString('en-IN', {minimumFractionDigits:2})}
            </span>
            <span class="stat-subtitle">Carries forward tomorrow</span>
          </div>
          <div class="oneui-card stat-card rose">
            <div class="stat-card-accent-bar"></div>
            <span class="stat-label">Total Monthly Expenses</span>
            <span class="stat-value">₹${totalExpenses.toLocaleString('en-IN', {minimumFractionDigits:2})}</span>
            <span class="stat-subtitle">Accumulated this month</span>
          </div>
          <div class="oneui-card stat-card amber">
            <div class="stat-card-accent-bar"></div>
            <span class="stat-label">Monthly Surplus Limit</span>
            <span class="stat-value">₹${remainingMonthlyBudget.toLocaleString('en-IN', {minimumFractionDigits:2})}</span>
            <span class="stat-subtitle">Projected savings margin</span>
          </div>
        </div>
        
        <!-- Charts breakdown -->
        <div class="oneui-card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-chart-pie" style="color: var(--primary);"></i> Expense Category Utilization</div>
          </div>
          <div style="height: 240px; display: flex; justify-content: center; align-items: center;">
            <canvas id="categoryChart"></canvas>
          </div>
        </div>
      </div>
      
      <!-- Right panel sidebar: Health ring, Active savings goals, AI Insight -->
      <div style="display: flex; flex-direction: column; gap: 24px;">
        <!-- Circular Health Rating -->
        <div class="oneui-card" style="text-align: center;">
          <div class="card-header" style="justify-content: center; margin-bottom: 20px;">
            <div class="card-title">Financial Health Rating</div>
          </div>
          <div class="health-score-ring">
            <svg width="120" height="120" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="50" fill="none" stroke="var(--bg-tertiary)" stroke-width="8"></circle>
              <circle cx="60" cy="60" r="50" fill="none" stroke="url(#healthGrad)" stroke-width="8"
                      stroke-dasharray="314.16" stroke-dashoffset="${314.16 - (314.16 * STATE.user.financial_health_score / 100)}"
                      stroke-linecap="round" transform="rotate(-90 60 60)"></circle>
              <defs>
                <linearGradient id="healthGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="var(--primary)"></stop>
                  <stop offset="100%" stop-color="var(--income)"></stop>
                </linearGradient>
              </defs>
            </svg>
            <span class="health-score-val">${STATE.user.financial_health_score}</span>
          </div>
          <p style="font-size: 14px; font-weight: 700; margin-top: 16px; color: ${STATE.user.financial_health_score >= 80 ? 'var(--income)' : STATE.user.financial_health_score >= 50 ? 'var(--warning)' : 'var(--expense)'}">
            ${STATE.user.financial_health_score >= 80 ? 'Excellent Status' : STATE.user.financial_health_score >= 50 ? 'Warning Level' : 'Critically Low'}
          </p>
          <p style="color: var(--text-secondary); font-size: 11px; margin-top: 4px;">Tracks tracking consistency, budget limits and saving rates.</p>
        </div>

        <!-- Savings Goals list -->
        <div class="oneui-card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-bullseye" style="color: var(--primary);"></i> Active Savings Goals</div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 14px;">
            ${STATE.goals.length === 0 ? `<p style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 10px;">No goals initialized yet.</p>` : ""}
            ${STATE.goals.slice(0, 3).map(g => {
              const progress = ((g.current_amount / g.target_amount) * 100).toFixed(1);
              return `
                <div>
                  <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 600;">
                    <span style="color: var(--text-primary); text-overflow: ellipsis; overflow: hidden; white-space: nowrap; max-width: 140px;">${g.title}</span>
                    <span style="color: var(--text-secondary);">₹${g.current_amount.toLocaleString()} (${progress}%)</span>
                  </div>
                  <div class="progress-bar-container">
                    <div class="progress-bar-fill" style="width: ${progress}%; background: linear-gradient(90deg, var(--primary), var(--secondary));"></div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- AI Engine insights container -->
        <div class="oneui-card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-robot" style="color: var(--primary);"></i> AI Intelligence Insights</div>
          </div>
          <div id="ai-recs-dashboard-container">
            <div style="text-align: center; padding: 20px; color: var(--text-secondary);"><i class="fas fa-spinner fa-spin"></i> Core analysis running...</div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Actions and Controls floating footer bar -->
    <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 24px;">
      <button class="btn" id="btn-export-report"><i class="fas fa-file-pdf"></i> Download Report</button>
      <button class="btn btn-primary" id="btn-quick-expense"><i class="fas fa-plus"></i> Record Expense</button>
    </div>
  `;

  // Draw Category chart
  const categoriesMap = {};
  STATE.transactions.filter(t => t.type === 'expense').forEach(t => {
    categoriesMap[t.category] = (categoriesMap[t.category] || 0) + t.amount;
  });

  const chartCtx = document.getElementById("categoryChart").getContext("2d");
  const chartLabels = Object.keys(categoriesMap);
  const chartData = Object.values(categoriesMap);
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  const legendTextColor = isDark ? "#98A2B3" : "#5E6472";

  if (chartLabels.length > 0) {
    STATE.activeCharts["category"] = new Chart(chartCtx, {
      type: "doughnut",
      data: {
        labels: chartLabels,
        datasets: [{
          data: chartData,
          backgroundColor: ["#1B6EF3", "#6F42C1", "#008080", "#00B074", "#FF3B30", "#FF9500", "#5856D6", "#FF2D55", "#4CD964"],
          borderWidth: 2,
          borderColor: isDark ? "#121316" : "#FFFFFF"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "right",
            labels: { color: legendTextColor, font: { family: "Plus Jakarta Sans", size: 11, weight: "500" } }
          }
        }
      }
    });
  } else {
    chartCtx.font = "14px Plus Jakarta Sans";
    chartCtx.fillStyle = legendTextColor;
    chartCtx.textAlign = "center";
    chartCtx.fillText("Record expenses to visualize spending breakdown", 150, 110);
  }

  // Load recommendations via API
  apiRequest("/api/recommendations").then(recs => {
    const recsMount = document.getElementById("ai-recs-dashboard-container");
    if (!recsMount) return;
    
    if (recs && recs.length > 0) {
      recsMount.innerHTML = `
        <div class="recommendation-list">
          ${recs.slice(0, 2).map(r => `
            <div class="rec-item">
              <i class="fas ${r.category === 'Food' ? 'fa-hamburger' : r.category === 'Shopping' ? 'fa-shopping-bag' : 'fa-lightbulb'} rec-icon"></i>
              <div>
                <div class="rec-text">${r.suggestion}</div>
                ${r.impact_amount > 0 ? `<div class="rec-impact">Savings Impact: +₹${r.impact_amount.toFixed(0)}/mo</div>` : ""}
              </div>
            </div>
          `).join('')}
        </div>
      `;
    } else {
      recsMount.innerHTML = `<p style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 10px;">Excellent discipline! No saving leaks detected.</p>`;
    }
  }).catch(() => {
    const recsMount = document.getElementById("ai-recs-dashboard-container");
    if (recsMount) recsMount.innerHTML = `<p style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 10px;">Failed to generate recommendations.</p>`;
  });

  // Action listeners
  document.getElementById("btn-quick-expense").addEventListener("click", showQuickExpenseModal);
  
  document.getElementById("btn-export-report").addEventListener("click", async () => {
    const today = new Date();
    const month = today.getMonth() + 1;
    const year = today.getFullYear();
    try {
      showToast("Generating report PDF...", "success");
      
      const response = await fetch(`/api/reports/monthly?month=${month}&year=${year}`, {
        headers: { "Authorization": `Bearer ${STATE.token}` }
      });
      
      if (!response.ok) {
        let errMsg = "Failed to generate report PDF";
        try {
          const errJSON = await response.json();
          errMsg = errJSON.detail || errMsg;
        } catch(e) {}
        throw new Error(errMsg);
      }
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `SafeMoney_Report_${year}_${month.toString().padStart(2, '0')}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      showToast("Report downloaded successfully!");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 2. Transactions Module Overhaul
function renderTransactions(mount) {
  mount.innerHTML = `
    <div class="grid-cols-3-layout">
      <!-- Record Transaction Card -->
      <div class="oneui-card" style="height: fit-content;">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-edit" style="color: var(--primary);"></i> Log Transaction</div>
        </div>
        <form id="tx-form">
          <div class="form-group">
            <label class="form-label">Transaction Type</label>
            <div style="display: flex; gap: 10px;">
              <label style="flex:1; padding:10px; border-radius:var(--border-radius-md); border:1px solid var(--card-border); display:flex; align-items:center; gap:8px; cursor:pointer;">
                <input type="radio" name="tx_type" value="expense" checked required> Expense
              </label>
              <label style="flex:1; padding:10px; border-radius:var(--border-radius-md); border:1px solid var(--card-border); display:flex; align-items:center; gap:8px; cursor:pointer;">
                <input type="radio" name="tx_type" value="income" required> Income
              </label>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Amount (₹)</label>
            <input type="number" id="tx-amount" class="form-control" placeholder="e.g. 500" min="1" required>
          </div>
          <div class="form-group" id="tx-cat-container">
            <label class="form-label">Category</label>
            <select id="tx-category" class="form-control">
              ${CATEGORIES.map(c => `<option value="${c}">${c}</option>`).join('')}
            </select>
          </div>
          <div class="form-group" id="tx-income-type-container" style="display: none;">
            <label class="form-label">Income Type</label>
            <select id="tx-income-type" class="form-control">
              <option value="Salary">Salary</option>
              <option value="Gift">Gift</option>
              <option value="Bonus">Bonus</option>
              <option value="Cashback">Cashback</option>
              <option value="Reward">Reward</option>
              <option value="Refund">Refund</option>
              <option value="Investment Return">Investment Return</option>
              <option value="Other">Other</option>
            </select>
          </div>
          <div class="form-group" id="tx-sender-container" style="display: none;">
            <label class="form-label">Sender (Optional)</label>
            <input type="text" id="tx-sender" class="form-control" placeholder="e.g. Mom, Google, Friend">
          </div>
          <div class="form-group">
            <label class="form-label">Description / Payee</label>
            <input type="text" id="tx-desc" class="form-control" placeholder="e.g. Amazon Grocery" required>
          </div>
          <div class="form-group">
            <label class="form-label">Payment Method</label>
            <select id="tx-method" class="form-control">
              <option value="UPI">UPI</option>
              <option value="Debit Card">Debit Card</option>
              <option value="Credit Card">Credit Card</option>
              <option value="Net Banking">Net Banking</option>
              <option value="Cash">Cash</option>
            </select>
          </div>
          <div class="grid-cols-2" style="margin-bottom: 0;">
            <div class="form-group">
              <label class="form-label">Date</label>
              <input type="date" id="tx-date" class="form-control" required>
            </div>
            <div class="form-group">
              <label class="form-label">Time</label>
              <input type="time" id="tx-time" class="form-control" required>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Notes (Optional)</label>
            <textarea id="tx-notes" class="form-control" placeholder="Additional details..." rows="2"></textarea>
          </div>
          <button type="submit" class="btn btn-primary" style="width: 100%;">Record Transaction</button>
        </form>
      </div>

      <!-- Transaction History Table Card -->
      <div class="oneui-card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-history" style="color: var(--primary);"></i> History Logs</div>
        </div>
        
        <div class="table-container">
          <table class="custom-table">
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>Description</th>
                <th>Category</th>
                <th>Method</th>
                <th>Amount (₹)</th>
                <th>Boost (₹)</th>
                <th>New Bal (₹)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.transactions.length === 0 ? `<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">No records found.</td></tr>` : ""}
              ${STATE.transactions.map(t => `
                <tr>
                  <td style="font-size:12px; white-space: nowrap;">${t.date}<br><span style="color:var(--text-muted)">${t.time}</span></td>
                  <td>
                    <div style="font-weight:700;">${t.description}</div>
                    ${t.sender ? `<span style="font-size:11px; padding: 2px 6px; border-radius: 4px; background: var(--income-glow); color: var(--income)">From: ${t.sender}</span>` : ""}
                    ${t.notes ? `<div style="font-size:11px; color:var(--text-secondary); font-style:italic;">${t.notes}</div>` : ""}
                  </td>
                  <td>
                    <span class="badge-pill ${t.type === 'income' ? 'badge-income' : 'badge-expense'}">
                      ${t.type === 'income' ? (t.income_type || 'Income') : t.category}
                    </span>
                  </td>
                  <td style="font-size:12px;">${t.payment_method}</td>
                  <td style="font-weight: 700; color: ${t.type === 'income' ? 'var(--income)' : 'var(--text-primary)'}">
                    ${t.type === 'income' ? '+' : '-'} ₹${t.amount.toLocaleString()}
                  </td>
                  <td style="font-weight: 600; color: var(--primary);">
                    ${t.budget_boost_amount && t.budget_boost_amount > 0 ? `+₹${t.budget_boost_amount.toLocaleString()}` : '—'}
                  </td>
                  <td style="font-size:13px; font-weight: 600; color: var(--text-secondary);">
                    ₹${(t.updated_balance !== undefined && t.updated_balance !== null ? t.updated_balance : STATE.user.current_balance).toLocaleString('en-IN', {minimumFractionDigits:2})}
                  </td>
                  <td>
                    <button class="btn btn-sm btn-danger btn-delete-tx" data-id="${t.id}" style="padding:6px 10px;"><i class="fas fa-trash"></i></button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  // Set default forms dates
  const now = new Date();
  document.getElementById("tx-date").value = now.toISOString().split('T')[0];
  document.getElementById("tx-time").value = now.toTimeString().split(' ')[0].substring(0, 5);

  // Toggle category triggers
  document.querySelectorAll("input[name='tx_type']").forEach(elem => {
    elem.addEventListener("change", (e) => {
      const catContainer = document.getElementById("tx-cat-container");
      const incomeTypeContainer = document.getElementById("tx-income-type-container");
      const senderContainer = document.getElementById("tx-sender-container");
      if (e.target.value === "income") {
        catContainer.style.display = "none";
        incomeTypeContainer.style.display = "block";
        senderContainer.style.display = "block";
      } else {
        catContainer.style.display = "block";
        incomeTypeContainer.style.display = "none";
        senderContainer.style.display = "none";
      }
    });
  });

  // Submit tx
  document.getElementById("tx-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const type = document.querySelector("input[name='tx_type']:checked").value;
    const amount = parseFloat(document.getElementById("tx-amount").value);
    const category = type === "income" ? "Income" : document.getElementById("tx-category").value;
    const description = document.getElementById("tx-desc").value;
    const payment_method = document.getElementById("tx-method").value;
    const date = document.getElementById("tx-date").value;
    const time = document.getElementById("tx-time").value;
    const notes = document.getElementById("tx-notes").value;
    const income_type = type === "income" ? document.getElementById("tx-income-type").value : null;
    const sender = type === "income" ? (document.getElementById("tx-sender").value.trim() || null) : null;

    try {
      await apiRequest("/api/transactions", "POST", {
        date, time, category, description, payment_method, amount, type, notes, income_type, sender
      });
      showToast("Transaction logged!");
      setView("transactions");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Delete Tx
  document.querySelectorAll(".btn-delete-tx").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const txId = e.currentTarget.dataset.id;
      if (confirm("Are you sure you want to delete this transaction? This will revert account balance adjustments.")) {
        try {
          await apiRequest(`/api/transactions/${txId}`, "DELETE");
          showToast("Transaction deleted successfully");
          setView("transactions");
        } catch (err) {
          showToast(err.message, "error");
        }
      }
    });
  });
}

// 3. Savings Goals Module Overhaul
function renderGoals(mount) {
  mount.innerHTML = `
    <div class="grid-cols-3-layout">
      <!-- Form card -->
      <div class="oneui-card" style="height: fit-content;">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-bullseye" style="color: var(--primary);"></i> Launch Savings Goal</div>
        </div>
        <form id="goal-form">
          <div class="form-group">
            <label class="form-label">Goal Title</label>
            <input type="text" id="goal-title" class="form-control" placeholder="e.g. Emergency Cash Pool" required>
          </div>
          <div class="form-group">
            <label class="form-label">Objective purpose</label>
            <select id="goal-purpose" class="form-control">
              <option value="Laptop">Purchase Laptop</option>
              <option value="Education">Funding Higher Education</option>
              <option value="Vehicle">Buying a Vehicle</option>
              <option value="Vacation">Planning a Vacation</option>
              <option value="Investment">Making Investments</option>
              <option value="Home">Purchasing a Home</option>
              <option value="Other">Other Objective</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Target Amount (₹)</label>
            <input type="number" id="goal-target" class="form-control" placeholder="e.g. 50000" min="100" required>
          </div>
          <div class="form-group">
            <label class="form-label">Target Date</label>
            <input type="date" id="goal-date" class="form-control" required>
          </div>
          <div class="form-group">
            <label class="form-label">Monthly Target contribution (₹)</label>
            <input type="number" id="goal-contribution" class="form-control" placeholder="e.g. 4000" min="0" required>
          </div>
          <button type="submit" class="btn btn-primary" style="width: 100%;">Create Savings Goal</button>
        </form>
      </div>

      <!-- Objectives portfolio list -->
      <div class="oneui-card">
        <div class="card-header" style="margin-bottom: 24px;">
          <div class="card-title"><i class="fas fa-award" style="color: var(--primary);"></i> Current Portfolios</div>
          <button class="btn btn-primary btn-sm" id="btn-allocate-savings-modal"><i class="fas fa-piggy-bank"></i> Allocate Funds</button>
        </div>
        
        <div style="display:flex; flex-direction:column; gap:20px;">
          ${STATE.goals.length === 0 ? `<p style="text-align:center; padding:30px; color:var(--text-muted)">No active goals established.</p>` : ""}
          ${STATE.goals.map(g => {
            const progress = ((g.current_amount / g.target_amount) * 100).toFixed(1);
            return `
              <div class="oneui-card" style="background: var(--bg-primary); padding: 18px; margin-bottom: 0;">
                <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom: 8px;">
                  <div>
                    <h4 style="font-size: 15px; color:var(--text-primary); font-weight:700;">${g.title}</h4>
                    <span style="font-size: 11px; color: var(--text-muted)">Category: <b>${g.purpose}</b> | Target Date: <b>${g.target_date}</b></span>
                  </div>
                  <span class="badge-pill" style="background: var(--primary-glow); color: var(--primary); border: 1px solid currentColor;">
                    ${g.status.toUpperCase()}
                  </span>
                </div>
                
                <div style="display:flex; justify-content:space-between; font-size:12px; margin: 12px 0 4px 0; color: var(--text-secondary);">
                  <span>Monthly Contribution: <b>₹${g.monthly_contribution.toLocaleString()}/mo</b></span>
                  <span>Progress: <b>₹${g.current_amount.toLocaleString()} / ₹${g.target_amount.toLocaleString()} (${progress}%)</b></span>
                </div>
                <div class="progress-bar-container">
                  <div class="progress-bar-fill" style="width: ${progress}%; background: linear-gradient(90deg, var(--primary), var(--secondary));"></div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    </div>
  `;

  // Date default set
  const futureDate = new Date();
  futureDate.setMonth(futureDate.getMonth() + 6);
  document.getElementById("goal-date").value = futureDate.toISOString().split('T')[0];

  // Submit Goal
  document.getElementById("goal-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("goal-title").value;
    const purpose = document.getElementById("goal-purpose").value;
    const target_amount = parseFloat(document.getElementById("goal-target").value);
    const target_date = document.getElementById("goal-date").value;
    const monthly_contribution = parseFloat(document.getElementById("goal-contribution").value);

    try {
      await apiRequest("/api/goals", "POST", {
        title, purpose, target_amount, target_date, monthly_contribution
      });
      showToast("Savings Goal created! Monthly budget recalculated.");
      setView("goals");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Allocate funds trigger modal
  document.getElementById("btn-allocate-savings-modal").addEventListener("click", () => {
    if (STATE.goals.length === 0) {
      showToast("Create a savings goal before allocating savings", "error");
      return;
    }
    showAllocateSavingsModal();
  });
}

// 4. What-If Simulator Overhaul
function renderSimulation(mount) {
  mount.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 20px; color: var(--text-primary);">Simulation Dashboard</h2>
      <p style="color: var(--text-secondary); font-size: 13px; margin-top: 4px;">Adjust hypothetical budget constraints to project saving timelines and score boosts.</p>
    </div>

    <div class="grid-cols-3-layout">
      <!-- Simulation Controls Panel -->
      <div class="oneui-card" style="height: fit-content;">
        <div class="card-header" style="margin-bottom: 20px;">
          <div class="card-title"><i class="fas fa-sliders-h" style="color: var(--primary);"></i> Control Variables</div>
        </div>
        
        <div class="slider-group">
          <div class="slider-label-container">
            <span>Cut Dining Out & Food Logs</span>
            <span id="label-food" style="font-weight:700; color:var(--primary);">0%</span>
          </div>
          <input type="range" id="sim-food" class="slider-control" min="0" max="100" value="0">
        </div>
        
        <div class="slider-group">
          <div class="slider-label-container">
            <span>Cut Online Shopping Logs</span>
            <span id="label-shopping" style="font-weight:700; color:var(--primary);">0%</span>
          </div>
          <input type="range" id="sim-shopping" class="slider-control" min="0" max="100" value="0">
        </div>
        
        <div class="slider-group">
          <div class="slider-label-container">
            <span>Cut Entertainment Logs</span>
            <span id="label-ent" style="font-weight:700; color:var(--primary);">0%</span>
          </div>
          <input type="range" id="sim-ent" class="slider-control" min="0" max="100" value="0">
        </div>
        
        <hr style="border: 0; border-top: 1px solid var(--card-border); margin: 20px 0;">
        
        <div class="form-group">
          <label class="form-label">Simulate Income Spike (₹/mo)</label>
          <input type="number" id="sim-income" class="form-control" placeholder="e.g. 5000" min="0" value="0">
        </div>
        
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Simulate Extra Savings contribution (₹/mo)</label>
          <input type="number" id="sim-savings" class="form-control" placeholder="e.g. 2000" min="0" value="0">
        </div>
      </div>

      <!-- Simulator Output Graphics -->
      <div class="oneui-card" style="display: flex; flex-direction: column; gap: 20px;">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-magic" style="color: var(--primary);"></i> Predictive Forecasting Analysis</div>
        </div>
        
        <div class="grid-cols-2" style="margin-bottom: 0; gap: 16px;">
          <!-- Budget Impact Card -->
          <div style="background: var(--bg-primary); padding: 18px; border-radius: var(--border-radius-lg); border: 1px solid var(--card-border);">
            <div style="color:var(--text-secondary); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.02em; margin-bottom: 6px;">Recommended Daily Spending Limit</div>
            <div style="display:flex; justify-content:space-between; align-items:baseline;">
              <span style="font-size:13px; text-decoration:line-through; color:var(--text-muted);" id="sim-val-current-daily">₹0.00</span>
              <span style="font-size:22px; font-weight:800; color:var(--primary);" id="sim-val-new-daily">₹0.00</span>
            </div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:6px;">Calculated limit recommendation.</div>
          </div>
          
          <!-- Annual Savings Impact Card -->
          <div style="background: var(--bg-primary); padding: 18px; border-radius: var(--border-radius-lg); border: 1px solid var(--card-border);">
            <div style="color:var(--text-secondary); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.02em; margin-bottom: 6px;">Simulated Annual Surplus Gain</div>
            <div style="display:flex; justify-content:space-between; align-items:baseline;">
              <span style="font-size:13px; color:var(--text-muted);" id="sim-val-current-monthly">₹0.00/mo</span>
              <span style="font-size:22px; font-weight:800; color:var(--income);" id="sim-val-new-annual">+₹0.00</span>
            </div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:6px;">Incremental annual forecast gain.</div>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 16px;">
          <!-- Health Score Projection Card -->
          <div style="background: var(--bg-primary); padding: 18px; border-radius: var(--border-radius-lg); border: 1px solid var(--card-border); text-align: center;">
            <div style="color:var(--text-secondary); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.02em; margin-bottom: 8px;">Projected Health Score</div>
            <div style="font-size:36px; font-weight:800; color:var(--income); line-height: 1.2;" id="sim-val-projected-health">0</div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:6px;">Target Health score projection</div>
          </div>
          
          <!-- Goals Accelerations list Card -->
          <div style="background: var(--bg-primary); padding: 18px; border-radius: var(--border-radius-lg); border: 1px solid var(--card-border);">
            <div style="color:var(--text-secondary); font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.02em; margin-bottom: 8px;"><i class="fas fa-rocket"></i> Savings Target Timelines Acceleration</div>
            <div id="sim-val-goals-speedup" style="display:flex; flex-direction:column; gap:6px;">
              <!-- Populated dynamically -->
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  // Bind live sliders variables
  const sliders = ["food", "shopping", "ent"];
  sliders.forEach(s => {
    const input = document.getElementById(`sim-${s}`);
    const label = document.getElementById(`label-${s}`);
    input.addEventListener("input", (e) => {
      label.innerText = `${e.target.value}%`;
      triggerSimulationRecalculation();
    });
  });

  document.getElementById("sim-income").addEventListener("input", triggerSimulationRecalculation);
  document.getElementById("sim-savings").addEventListener("input", triggerSimulationRecalculation);

  // Trigger default calc
  triggerSimulationRecalculation();
}

async function triggerSimulationRecalculation() {
  const foodPct = parseFloat(document.getElementById("sim-food").value);
  const shopPct = parseFloat(document.getElementById("sim-shopping").value);
  const entPct = parseFloat(document.getElementById("sim-ent").value);
  const extraIncome = parseFloat(document.getElementById("sim-income").value) || 0.0;
  const extraSavings = parseFloat(document.getElementById("sim-savings").value) || 0.0;

  try {
    const response = await apiRequest("/api/simulate", "POST", {
      reduce_categories: {
        "Food": foodPct,
        "Shopping": shopPct,
        "Entertainment": entPct
      },
      increase_income: extraIncome,
      target_savings_increase: extraSavings
    });

    document.getElementById("sim-val-current-daily").innerText = `₹${response.current_daily_budget.toLocaleString('en-IN', {maximumFractionDigits:2})}`;
    document.getElementById("sim-val-new-daily").innerText = `₹${response.new_daily_budget.toLocaleString('en-IN', {maximumFractionDigits:2})}`;
    document.getElementById("sim-val-current-monthly").innerText = `Current: ₹${response.current_monthly_savings.toLocaleString()}/mo`;
    document.getElementById("sim-val-new-annual").innerText = `+₹${response.projected_annual_savings_increase.toLocaleString('en-IN', {maximumFractionDigits:0})}/yr`;
    document.getElementById("sim-val-projected-health").innerText = response.financial_health_impact;

    const listContainer = document.getElementById("sim-val-goals-speedup");
    listContainer.innerHTML = response.goals_impact.map(gi => `
      <div style="display:flex; justify-content:space-between; font-size:12px; border-bottom:1px solid var(--card-border); padding-bottom:4px;">
        <span style="font-weight: 500;">${gi.goal}</span>
        <span style="color:var(--income); font-weight:700;">${gi.impact}</span>
      </div>
    `).join('') || `<span style="font-size:11px; color:var(--text-muted)">Configure active savings goals to track timelines.</span>`;

  } catch (err) {
    console.error("Simulation error:", err);
  }
}

// 5. Gamification and Challenges Module Overhaul
function renderGamification(mount) {
  const gam = STATE.gamification;
  mount.innerHTML = `
    <!-- Top Level XP Stats Cards Grid -->
    <div class="grid-cols-3" style="margin-bottom: 24px;">
      <div class="oneui-card" style="text-align:center;">
        <span style="color:var(--text-secondary); font-size:12px; font-weight:600; text-transform:uppercase;">Discipline Points Balance</span>
        <div style="font-size:32px; font-weight:800; font-family:var(--font-heading); color:#FF9500; margin: 8px 0;"><i class="fas fa-coins"></i> ${gam.points} XP</div>
        <span style="font-size:11px; color:var(--text-muted);">Redeemable for leaderboard rankings</span>
      </div>
      <div class="oneui-card" style="text-align:center;">
        <span style="color:var(--text-secondary); font-size:12px; font-weight:600; text-transform:uppercase;">Expense Streak Score</span>
        <div style="font-size:32px; font-weight:800; font-family:var(--font-heading); color:var(--primary); margin: 8px 0;"><i class="fas fa-fire"></i> ${gam.streak_days} Days</div>
        <span style="font-size:11px; color:var(--text-muted);">Log transactions regularly to boost multipliers</span>
      </div>
      <div class="oneui-card" style="text-align:center;">
        <span style="color:var(--text-secondary); font-size:12px; font-weight:600; text-transform:uppercase;">Milestone Achievements</span>
        <div style="font-size:32px; font-weight:800; font-family:var(--font-heading); color:var(--income); margin: 8px 0;"><i class="fas fa-award"></i> ${gam.badges.length}</div>
        <span style="font-size:11px; color:var(--text-muted);">Total milestones achieved</span>
      </div>
    </div>

    <!-- Active Monthly Challenges container -->
    <div class="oneui-card" style="margin-bottom: 24px;">
      <div class="card-header" style="margin-bottom: 20px;">
        <div class="card-title"><i class="fas fa-tasks" style="color: var(--primary);"></i> Active System Challenges</div>
      </div>
      
      <div class="challenges-feed-container" style="display:flex; flex-direction:column; gap:12px;">
        ${gam.challenges.map(chall => {
          const activeUserChall = gam.user_challenges.find(uc => uc.challenge_id === chall.id);
          
          let actionBtn = "";
          if (activeUserChall) {
            actionBtn = `<span class="badge-pill" style="background:var(--income-glow); color:var(--income); border:1px solid var(--income); padding:6px 12px;">
              ${activeUserChall.status.toUpperCase()} (End: ${activeUserChall.end_date})
            </span>`;
          } else {
            actionBtn = `<button class="btn btn-sm btn-primary btn-join-challenge" data-id="${chall.id}">Join Challenge</button>`;
          }
          
          return `
            <div class="oneui-card" style="background:var(--bg-primary); display:flex; justify-content:space-between; align-items:center; padding: 16px 20px; margin-bottom: 0;">
              <div>
                <h4 style="font-size: 14px; color: var(--text-primary); font-weight: 700;">${chall.title}</h4>
                <p style="font-size: 12px; color: var(--text-secondary); margin-top:2px;">${chall.description}</p>
                <div style="font-size: 11px; color: var(--text-muted); margin-top:6px;">Reward: <b style="color:#FF9500">+${chall.points_reward} XP</b> | Limit Time: <b>${chall.duration_days} Days</b></div>
              </div>
              <div>
                ${actionBtn}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </div>

    <div class="grid-cols-2" style="margin-bottom: 0;">
      <!-- Achievements showcase cabinet -->
      <div class="oneui-card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-trophy" style="color: var(--primary);"></i> Achievements Cabinet</div>
        </div>
        <div class="badges-showcase">
          ${gam.badges.length === 0 ? `<p style="color:var(--text-muted); font-size:12px;">Complete challenges to earn reward badges.</p>` : ""}
          ${gam.badges.map(b => `
            <div class="badge-card" style="width: 100%;">
              <div class="badge-card-icon"><i class="fas fa-medal"></i></div>
              <div>
                <div class="badge-card-title">${b.name}</div>
                <div class="badge-card-desc">${b.description}</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- XP Points Audit logs -->
      <div class="oneui-card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-history" style="color: var(--primary);"></i> Points Audit trails</div>
        </div>
        <div style="display:flex; flex-direction:column; gap:10px; max-height: 300px; overflow-y: auto; padding-right: 4px;">
          ${gam.points_history.length === 0 ? `<p style="color:var(--text-muted); font-size:12px;">No logged activities found.</p>` : ""}
          ${gam.points_history.map(p => `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid var(--card-border); font-size:12px;">
              <div>
                <div style="font-weight: 600; color: var(--text-primary);">${p.reason}</div>
                <div style="font-size:10px; color:var(--text-muted);">${p.date}</div>
              </div>
              <span style="font-weight:700; color: ${p.points_change > 0 ? 'var(--income)' : 'var(--expense)'}">
                ${p.points_change > 0 ? '+' : ''}${p.points_change} XP
              </span>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;

  // Register Join button click listeners
  document.querySelectorAll(".btn-join-challenge").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const challengeId = e.currentTarget.dataset.id;
      try {
        await apiRequest(`/api/challenges/${challengeId}/join`, "POST");
        showToast("Joined challenge! Log transactions to complete metrics.");
        setView("gamification");
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });
}

// 6. Admin Portal Governance Module Overhaul
function renderAdmin(mount) {
  const stats = STATE.adminStats;
  const dbHealth = STATE.adminDb;
  
  mount.innerHTML = `
    <!-- Top-level quick stats cards -->
    <div class="grid-cols-4" style="margin-bottom: 24px;">
      <div class="oneui-card stat-card blue">
        <div class="stat-card-accent-bar"></div>
        <span class="stat-label">Total platform Users</span>
        <span class="stat-value">${stats.total_users}</span>
        <span class="stat-subtitle">Registered Member accounts</span>
      </div>
      <div class="oneui-card stat-card emerald">
        <div class="stat-card-accent-bar"></div>
        <span class="stat-label">Avg Health Index</span>
        <span class="stat-value">${stats.avg_health_score}/100</span>
        <span class="stat-subtitle">Platform health average</span>
      </div>
      <div class="oneui-card stat-card rose">
        <div class="stat-card-accent-bar"></div>
        <span class="stat-label">Average Saving Rate</span>
        <span class="stat-value">${stats.avg_savings_rate}%</span>
        <span class="stat-subtitle">Monthly surplus proportion</span>
      </div>
      <div class="oneui-card stat-card amber">
        <div class="stat-card-accent-bar"></div>
        <span class="stat-label">Platform operations Vol</span>
        <span class="stat-value">${stats.total_transactions} txs</span>
        <span class="stat-subtitle">Total logged logs</span>
      </div>
    </div>

    <!-- Governance lists layout -->
    <div class="grid-cols-3-layout">
      <!-- Users control list card -->
      <div class="oneui-card">
        <div class="card-header">
          <div class="card-title"><i class="fas fa-users-cog" style="color: var(--primary);"></i> Account Governance</div>
        </div>
        <div class="table-container">
          <table class="custom-table" style="font-size:13px;">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Health Score</th>
                <th>XP Points</th>
                <th>Balance (₹)</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.adminUsers.map(u => `
                <tr>
                  <td>
                    <div style="font-weight:700;">${u.username}</div>
                    <span style="font-size:10px; color:var(--text-muted)">${u.email}</span>
                  </td>
                  <td>
                    <span class="badge-pill" style="background: var(--primary-glow); color: var(--primary); font-size:10px;">
                      ${u.role.toUpperCase()}
                    </span>
                  </td>
                  <td style="font-weight:700; color: ${u.financial_health_score >= 80 ? 'var(--income)' : 'var(--warning)'}">${u.financial_health_score}</td>
                  <td>${u.points} XP</td>
                  <td>₹${u.current_balance.toLocaleString()}</td>
                  <td>
                    <button class="btn btn-sm btn-toggle-role" data-id="${u.id}" style="padding:4px 8px; font-size:11px;">Toggle Role</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right Column: Database Health and Deploy Challenge forms -->
      <div style="display:flex; flex-direction:column; gap:24px;">
        <!-- Database Health status card -->
        <div class="oneui-card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-server" style="color: var(--primary);"></i> System Status</div>
          </div>
          <div style="font-size:13px; display:flex; flex-direction:column; gap:8px; color: var(--text-secondary);">
            <div>Relational Database: <b style="color: var(--text-primary);">${dbHealth.database_type}</b></div>
            <div>File Size: <b style="color: var(--text-primary);">${dbHealth.size_kb} KB</b></div>
            <div>Database Status: <span class="badge-pill badge-income" style="font-size:9px;">Active / Healthy</span></div>
            <div style="font-size:11px; color:var(--text-muted); word-break:break-all;">Path: ${dbHealth.filepath}</div>
          </div>
        </div>

        <!-- Launch monthly challenge form card -->
        <div class="oneui-card">
          <div class="card-header">
            <div class="card-title"><i class="fas fa-plus" style="color: var(--primary);"></i> Deploy Challenge</div>
          </div>
          <form id="create-challenge-form">
            <div class="form-group">
              <label class="form-label">Challenge Title</label>
              <input type="text" id="chall-title" class="form-control" placeholder="e.g. Frugal Weekend" required>
            </div>
            <div class="form-group">
              <label class="form-label">Description / Guidelines</label>
              <input type="text" id="chall-desc" class="form-control" placeholder="Goal criteria..." required>
            </div>
            <div class="grid-cols-2" style="margin-bottom: 12px;">
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">XP Reward</label>
                <input type="number" id="chall-points" class="form-control" value="100" min="10" required>
              </div>
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">Days Duration</label>
                <input type="number" id="chall-days" class="form-control" value="7" min="1" required>
              </div>
            </div>
            <div class="grid-cols-2" style="margin-bottom: 16px;">
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">Target Type</label>
                <select id="chall-type" class="form-control">
                  <option value="spend_limit">Spend Limit</option>
                  <option value="no_category">No Shopping Category</option>
                  <option value="daily_savings">Daily Savings target</option>
                  <option value="zero_overspend">Zero Overspend</option>
                </select>
              </div>
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">Target Value (₹)</label>
                <input type="number" id="chall-val" class="form-control" value="100" required>
              </div>
            </div>
            <button type="submit" class="btn btn-primary" style="width:100%;">Deploy Challenge</button>
          </form>
        </div>
      </div>
    </div>

    <!-- Operations Security & governance audit trails logs card -->
    <div class="oneui-card" style="margin-top:24px;">
      <div class="card-header">
        <div class="card-title"><i class="fas fa-shield-alt" style="color: var(--primary);"></i> Security Operations Audit Trail</div>
      </div>
      <div class="table-container" style="max-height: 250px; overflow-y: auto;">
        <table class="custom-table" style="font-size:12px;">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Username</th>
              <th>Action Details</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${STATE.adminLogs.map(l => `
              <tr>
                <td style="white-space: nowrap;">${new Date(l.timestamp).toLocaleString()}</td>
                <td><b>${l.username || 'Anonymous'}</b></td>
                <td>${l.action}</td>
                <td>
                  <span class="badge-pill ${l.status === 'success' ? 'badge-income' : 'badge-expense'}">
                    ${l.status.toUpperCase()}
                  </span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Bind role triggers toggle
  document.querySelectorAll(".btn-toggle-role").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      const uId = e.target.dataset.id;
      try {
        await apiRequest(`/api/admin/users/${uId}/status`, "POST");
        showToast("User role toggled successfully");
        setView("admin");
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  // Deploy Challenge submit
  document.getElementById("create-challenge-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("chall-title").value;
    const description = document.getElementById("chall-desc").value;
    const points_reward = parseInt(document.getElementById("chall-points").value);
    const duration_days = parseInt(document.getElementById("chall-days").value);
    const target_type = document.getElementById("chall-type").value;
    const target_value = parseFloat(document.getElementById("chall-val").value);

    try {
      await apiRequest("/api/admin/challenges", "POST", {
        title, description, points_reward, target_type, target_value, duration_days
      });
      showToast("New challenge deployed successfully");
      setView("admin");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 7. Settings Module Overhaul
function renderSettings(mount) {
  mount.innerHTML = `
    <div style="margin-bottom: 24px;">
      <h2 style="font-size: 20px; color: var(--text-primary);">Feature Preferences</h2>
      <p style="color: var(--text-secondary); font-size: 13px; margin-top: 4px;">Customize specific algorithms triggers, display themes, and account characteristics.</p>
    </div>

    <div class="grid-cols-2" style="margin-bottom: 24px;">
      <!-- Toggle sliders card -->
      <div class="oneui-card">
        <div class="card-header" style="margin-bottom: 20px;">
          <div class="card-title"><i class="fas fa-toggle-on" style="color: var(--primary);"></i> Feature Automation</div>
        </div>
        
        <div style="display: flex; flex-direction: column; gap: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 16px; border-bottom: 1px solid var(--card-border);">
            <div>
              <h4 style="font-size: 14px; font-weight: 700; color: var(--text-primary);">Smart Gift Budget Boost</h4>
              <p style="font-size: 12px; color: var(--text-secondary); margin-top: 4px; max-width: 260px;">
                Automatically boosts your rolling daily budget limits whenever unexpected income logs (Gifts, Cashback, Rewards) are registered.
              </p>
            </div>
            <label class="switch-container">
              <input type="checkbox" id="toggle-gift-boost" ${STATE.user.gift_budget_boost_enabled ? 'checked' : ''}>
              <span class="slider-round"></span>
            </label>
          </div>
          
          <div style="font-size: 11px; color: var(--text-muted);">
            * Note: If deactivated, qualifying income logs will update your liquidity balance but will not boost rolling daily targets.
          </div>
        </div>
      </div>

      <!-- UI theme toggle selectors card -->
      <div class="oneui-card">
        <div class="card-header" style="margin-bottom: 20px;">
          <div class="card-title"><i class="fas fa-palette" style="color: var(--primary);"></i> Display Theme Preference</div>
        </div>
        
        <div style="display: flex; flex-direction: column; gap: 16px;">
          <label style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border:1px solid var(--card-border); border-radius:var(--border-radius-md); cursor:pointer;">
            <div>
              <div style="font-weight:700; font-size:13px; color: var(--text-primary);"><i class="fas fa-circle-half-stroke" style="margin-right:8px;"></i> System Default Theme</div>
              <div style="font-size:11px; color:var(--text-secondary);">Sync styles automatically with your system settings</div>
            </div>
            <input type="radio" name="settings_theme" value="system" ${STATE.theme === 'system' ? 'checked' : ''}>
          </label>
          
          <label style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border:1px solid var(--card-border); border-radius:var(--border-radius-md); cursor:pointer;">
            <div>
              <div style="font-weight:700; font-size:13px; color: var(--text-primary);"><i class="fas fa-sun" style="margin-right:8px;"></i> Premium Light Theme</div>
              <div style="font-size:11px; color:var(--text-secondary);">Bright visual controls, soft contrasts</div>
            </div>
            <input type="radio" name="settings_theme" value="light" ${STATE.theme === 'light' ? 'checked' : ''}>
          </label>
          
          <label style="display:flex; justify-content:space-between; align-items:center; padding:12px 16px; border:1px solid var(--card-border); border-radius:var(--border-radius-md); cursor:pointer;">
            <div>
              <div style="font-weight:700; font-size:13px; color: var(--text-primary);"><i class="fas fa-moon" style="margin-right:8px;"></i> Premium Dark Theme</div>
              <div style="font-size:11px; color:var(--text-secondary);">High contrast black screens, optimized for night</div>
            </div>
            <input type="radio" name="settings_theme" value="dark" ${STATE.theme === 'dark' ? 'checked' : ''}>
          </label>
        </div>
      </div>
    </div>

    <!-- Financial Profile Settings Card -->
    <div class="oneui-card" style="margin-bottom: 0;">
      <div class="card-header" style="margin-bottom: 20px;">
        <div class="card-title"><i class="fas fa-wallet" style="color: var(--primary);"></i> Financial Profile Parameters</div>
      </div>
      
      <form id="profile-parameters-form">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px;">
          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Monthly Income (₹)</label>
            <input type="number" id="settings-income" class="form-control" value="${STATE.user ? STATE.user.monthly_income : 0}" min="0" required>
          </div>
          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Recurring Monthly Expenses (₹)</label>
            <input type="number" id="settings-recurring" class="form-control" value="${STATE.user ? STATE.user.recurring_expenses : 0}" min="0" required>
          </div>
          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Monthly Reserved Amount (₹)</label>
            <input type="number" id="settings-reserved" class="form-control" value="${STATE.user ? STATE.user.reserved_amount : 0}" min="0" required>
          </div>
          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Current Account Balance (₹)</label>
            <input type="number" id="settings-balance" class="form-control" value="${STATE.user ? STATE.user.current_balance : 0}" min="0" required>
          </div>
        </div>
        <button type="submit" class="btn btn-primary" style="padding: 10px 20px;">Save Profile Settings</button>
      </form>
    </div>
  `;

  // Bind automation switch triggers
  document.getElementById("toggle-gift-boost").addEventListener("change", async (e) => {
    const isEnabled = e.target.checked;
    try {
      const response = await apiRequest("/api/settings", "POST", { gift_budget_boost_enabled: isEnabled });
      STATE.user.gift_budget_boost_enabled = response.gift_budget_boost_enabled;
      showToast(response.gift_budget_boost_enabled ? "Smart Gift Budget Boost enabled!" : "Smart Gift Budget Boost disabled!");
    } catch (err) {
      e.target.checked = !isEnabled;
      showToast(err.message, "error");
    }
  });

  // Bind display themes radio selectors
  document.querySelectorAll("input[name='settings_theme']").forEach(radio => {
    radio.addEventListener("change", (e) => {
      STATE.theme = e.target.value;
      localStorage.setItem("safemoney_theme", STATE.theme);
      applyTheme();
      render(); // Refresh shell UI colors instantly
      showToast(`Applied theme selection: ${STATE.theme.toUpperCase()}`);
    });
  });

  // Bind profile variables form submit
  document.getElementById("profile-parameters-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const income = parseFloat(document.getElementById("settings-income").value);
    const recurring = parseFloat(document.getElementById("settings-recurring").value);
    const reserved = parseFloat(document.getElementById("settings-reserved").value);
    const balance = parseFloat(document.getElementById("settings-balance").value);
    
    try {
      const response = await apiRequest("/api/profile/update", "POST", {
        monthly_income: income,
        recurring_expenses: recurring,
        reserved_amount: reserved,
        current_balance: balance
      });
      
      // Update local state variables
      if (STATE.user) {
        STATE.user.monthly_income = response.monthly_income;
        STATE.user.recurring_expenses = response.recurring_expenses;
        STATE.user.reserved_amount = response.reserved_amount;
        STATE.user.current_balance = response.current_balance;
      }
      
      showToast("Financial profile parameters updated successfully!");
      setView("settings");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}


// =================== DIALOGS AND OVERLAYS OVERHAULS ===================

// 1. Center-anchored Quick Expense modal Dialog
function showQuickExpenseModal() {
  const overlay = document.createElement("div");
  overlay.className = "dialog-overlay";
  
  overlay.innerHTML = `
    <div class="dialog-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3 style="font-family: var(--font-heading); color: var(--text-primary); display: flex; align-items: center; gap: 8px;">
          <i class="fas fa-wallet" style="color: var(--expense);"></i> Quick Record Expense
        </h3>
        <button id="close-modal" style="background:none; border:none; color:var(--text-muted); font-size: 18px; cursor:pointer;"><i class="fas fa-times"></i></button>
      </div>
      
      <form id="quick-expense-form">
        <div class="form-group">
          <label class="form-label">Amount (₹)</label>
          <input type="number" id="modal-amount" class="form-control" placeholder="e.g. 250" min="1" required>
        </div>
        <div class="form-group">
          <label class="form-label">Category</label>
          <select id="modal-category" class="form-control">
            ${CATEGORIES.map(c => `<option value="${c}">${c}</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Description / Vendor</label>
          <input type="text" id="modal-desc" class="form-control" placeholder="Starbucks Coffee" required>
        </div>
        <div class="form-group">
          <label class="form-label">Payment Method</label>
          <select id="modal-method" class="form-control">
            <option value="UPI">UPI Payment</option>
            <option value="Debit Card">Debit Card</option>
            <option value="Credit Card">Credit Card</option>
            <option value="Net Banking">Net Banking</option>
            <option value="Cash">Cash</option>
          </select>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%; padding:12px; margin-top:10px;">Save Transaction</button>
      </form>
    </div>
  `;

  document.body.appendChild(overlay);

  const close = () => {
    overlay.style.opacity = "0";
    overlay.querySelector(".dialog-card").style.transform = "scale(0.92)";
    setTimeout(() => overlay.remove(), 200);
  };
  
  document.getElementById("close-modal").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

  document.getElementById("quick-expense-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const amount = parseFloat(document.getElementById("modal-amount").value);
    const category = document.getElementById("modal-category").value;
    const description = document.getElementById("modal-desc").value;
    const payment_method = document.getElementById("modal-method").value;
    
    const now = new Date();
    const date = now.toISOString().split('T')[0];
    const time = now.toTimeString().split(' ')[0].substring(0, 5);

    try {
      await apiRequest("/api/transactions", "POST", {
        date, time, category, description, payment_method, amount, type: "expense"
      });
      showToast("Expense logged successfully! Points added.");
      close();
      setView("dashboard");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// 2. Center-anchored Allocate Savings modal Dialog
function showAllocateSavingsModal() {
  const overlay = document.createElement("div");
  overlay.className = "dialog-overlay";
  
  overlay.innerHTML = `
    <div class="dialog-card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h3 style="font-family: var(--font-heading); color: var(--text-primary); display: flex; align-items: center; gap: 8px;">
          <i class="fas fa-piggy-bank" style="color: var(--primary);"></i> Allocate Available Cash
        </h3>
        <button id="close-allocate" style="background:none; border:none; color:var(--text-muted); font-size: 18px; cursor:pointer;"><i class="fas fa-times"></i></button>
      </div>
      
      <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 16px;">Available Liquid Cash: <b>₹${STATE.user.current_balance.toLocaleString()}</b></p>
      
      <form id="allocate-savings-form">
        <div class="form-group">
          <label class="form-label">Target Savings Goal</label>
          <select id="allocate-goal-id" class="form-control">
            ${STATE.goals.filter(g => g.status === 'active').map(g => `<option value="${g.id}">${g.title} (Target: ₹${g.target_amount.toLocaleString()})</option>`).join('')}
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Transfer Amount (₹)</label>
          <input type="number" id="allocate-amount" class="form-control" placeholder="e.g. 5000" min="1" max="${STATE.user.current_balance}" required>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%; padding:12px; margin-top:10px;">Allocate Cash</button>
      </form>
    </div>
  `;

  document.body.appendChild(overlay);

  const close = () => {
    overlay.style.opacity = "0";
    overlay.querySelector(".dialog-card").style.transform = "scale(0.92)";
    setTimeout(() => overlay.remove(), 200);
  };
  
  document.getElementById("close-allocate").addEventListener("click", close);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });

  document.getElementById("allocate-savings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const goalId = document.getElementById("allocate-goal-id").value;
    const amount = parseFloat(document.getElementById("allocate-amount").value);

    try {
      await apiRequest(`/api/goals/${goalId}/add-savings?amount=${amount}`, "POST");
      showToast("Savings allocated successfully! Goal updated.");
      close();
      setView("goals");
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}


// =================== WINDOW RUNTIME INITIALIZATION ===================
window.addEventListener("DOMContentLoaded", () => {
  STATE.authMode = "login";
  render();
});
