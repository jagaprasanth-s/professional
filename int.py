const API_BASE = window.location.origin;

let state = {
  user: null,
  activeView: 'login',
  uploadMode: 'file',
  selectedFile: null,
  cachedChunks: [],
  cachedDocs: []
};

document.addEventListener('DOMContentLoaded', () => {
  const savedUser = localStorage.getItem('skillrag_session');
  if (savedUser) {
    try {
      state.user = JSON.parse(savedUser);
      navigateView(state.user.role === 'admin' ? 'admin' : 'user');
    } catch (e) {
      localStorage.removeItem('skillrag_session');
      navigateView('login');
    }
  } else {
    navigateView('login');
  }
  lucide.createIcons();
});

function navigateView(viewName) {
  state.activeView = viewName;
  const loginView = document.getElementById('loginView');
  const adminView = document.getElementById('adminView');
  const userView = document.getElementById('userView');
  const navbar = document.getElementById('mainNavbar');

  loginView.classList.add('hidden');
  adminView.classList.add('hidden');
  userView.classList.add('hidden');

  if (viewName === 'login') {
    navbar.classList.add('hidden');
    loginView.classList.remove('hidden');
  } else {
    navbar.classList.remove('hidden');
    updateNavbarState();
    if (viewName === 'admin') {
      adminView.classList.remove('hidden');
      refreshAdminData();
    } else if (viewName === 'user') {
      userView.classList.remove('hidden');
      loadUserSkillsTaxonomy();
      loadQueryHistory();
    }
  }
  setTimeout(() => lucide.createIcons(), 50);
}

function updateNavbarState() {
  if (!state.user) return;
  document.getElementById('navUserName').textContent = state.user.name;
  document.getElementById('navUserRole').textContent = state.user.role.toUpperCase();
  
  const navUserTab = document.getElementById('navUserTab');
  const navAdminTab = document.getElementById('navAdminTab');

  if (state.activeView === 'user') {
    navUserTab.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white shadow-sm transition-all";
    navAdminTab.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all";
  } else {
    navAdminTab.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white shadow-sm transition-all";
    navUserTab.className = "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all";
  }
  fetchAdminStatsForNav();
}

async function fetchAdminStatsForNav() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/stats`);
    if (res.ok) {
      const stats = await res.json();
      document.getElementById('navDbCount').textContent = `${stats.total_chunks || 0} Chunks in SQLite`;
      document.getElementById('dbStatusPill').classList.remove('hidden');
    }
  } catch (e) {}
}

function switchDashboard(targetRole) {
  if (!state.user) {
    navigateView('login');
    return;
  }
  navigateView(targetRole);
}

function navigateHome() {
  if (!state.user) {
    navigateView('login');
  } else {
    navigateView(state.user.role === 'admin' ? 'admin' : 'user');
  }
}

async function loginAs(role) {
  try {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: role })
    });
    const data = await res.json();
    if (data.success) {
      state.user = data.user;
      localStorage.setItem('skillrag_session', JSON.stringify(state.user));
      showToast(`Welcome! Logged in as ${data.user.name}`, 'success');
      navigateView(role === 'admin' ? 'admin' : 'user');
    }
  } catch (e) {
    state.user = {
      name: role === 'admin' ? 'Admin Curator' : 'Professional User',
      role: role,
      token: 'demo-token'
    };
    localStorage.setItem('skillrag_session', JSON.stringify(state.user));
    navigateView(role);
  }
}

function handleLogout() {
  state.user = null;
  localStorage.removeItem('skillrag_session');
  showToast('Logged out successfully', 'info');
  navigateView('login');
}

async function refreshAdminData() {
  try {
    const [statsRes, docsRes, chunksRes] = await Promise.all([
      fetch(`${API_BASE}/api/admin/stats`),
      fetch(`${API_BASE}/api/admin/documents`),
      fetch(`${API_BASE}/api/admin/chunks?limit=200`)
    ]);

    if (statsRes.ok) renderAdminStats(await statsRes.json());
    if (docsRes.ok) {
      state.cachedDocs = await docsRes.json();
      renderDocumentsTable(state.cachedDocs);
    }
    if (chunksRes.ok) {
      state.cachedChunks = await chunksRes.json();
      renderChunksInspector(state.cachedChunks);
    }
    fetchAdminStatsForNav();
  } catch (e) {
    showToast('Failed to fetch admin data', 'error');
  }
}

function renderAdminStats(stats) {
  document.getElementById('statTotalDocs').textContent = stats.total_documents || 0;
  document.getElementById('statTotalChunks').textContent = stats.total_chunks || 0;
  document.getElementById('statTotalCategories').textContent = stats.total_categories || 0;
  document.getElementById('statTotalSkills').textContent = stats.total_skills || 0;

  const container = document.getElementById('categoryDistributionList');
  container.innerHTML = '';
  
  if (!stats.category_breakdown || stats.category_breakdown.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 italic">No categories indexed yet.</p>';
    return;
  }

  const maxCount = Math.max(...stats.category_breakdown.map(c => c.count), 1);
  stats.category_breakdown.forEach(cat => {
    const pct = Math.round((cat.count / maxCount) * 100);
    const item = document.createElement('div');
    item.className = 'space-y-1';
    item.innerHTML = `
      <div class="flex items-center justify-between text-xs">
        <span class="text-slate-300 font-medium truncate max-w-[180px]">${cat.category}</span>
        <span class="text-slate-400 font-mono text-[11px]">${cat.count} chunks</span>
      </div>
      <div class="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
        <div class="bg-gradient-to-r from-indigo-500 to-sky-400 h-1.5 rounded-full" style="width: ${pct}%"></div>
      </div>
    `;
    container.appendChild(item);
  });
}

function renderDocumentsTable(docs) {
  const tbody = document.getElementById('docsTableBody');
  tbody.innerHTML = '';

  if (!docs || docs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-8 text-center text-slate-500">
          <p>No documents uploaded yet. Click "Upload New Standard" or "Load Official Sample Frameworks".</p>
        </td>
      </tr>
    `;
    return;
  }

  docs.forEach(d => {
    const tr = document.createElement('tr');
    tr.className = 'hover:bg-slate-800/40 transition-colors';
    const dateFormatted = d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Recent';
    const sizeKb = d.file_size ? `${Math.round(d.file_size / 1024)} KB` : 'N/A';

    tr.innerHTML = `
      <td class="py-3 px-3">
        <div class="flex items-center gap-2">
          <i data-lucide="file-text" class="w-4 h-4 text-indigo-400 shrink-0"></i>
          <div>
            <div class="font-semibold text-slate-200">${d.filename}</div>
            <div class="text-[10px] text-slate-500">${sizeKb}</div>
          </div>
        </div>
      </td>
      <td class="py-3 px-3">
        <span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
          ${d.framework || 'Occupational Standard'}
        </span>
      </td>
      <td class="py-3 px-3 font-mono font-semibold text-indigo-400">
        ${d.total_chunks || d.chunk_count || 0}
      </td>
      <td class="py-3 px-3 text-slate-400 text-[11px]">
        ${dateFormatted}
      </td>
      <td class="py-3 px-3 text-right">
        <button onclick="handleDeleteDoc(${d.id})" class="p-1.5 rounded hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 transition-colors">
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
  lucide.createIcons();
}

function renderChunksInspector(chunks) {
  const container = document.getElementById('chunksInspectorContainer');
  container.innerHTML = '';

  if (!chunks || chunks.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 italic col-span-3 py-6 text-center">No chunks match filter.</p>';
    return;
  }

  chunks.forEach(c => {
    const card = document.createElement('div');
    card.className = 'rounded-xl bg-slate-950/70 border border-slate-800/80 p-4 hover:border-indigo-500/40 transition-all flex flex-col justify-between';
    
    let relatedBadges = '';
    if (Array.isArray(c.related_skills) && c.related_skills.length > 0) {
      relatedBadges = c.related_skills.map(s => `<span class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[10px] text-slate-400">${s}</span>`).join('');
    }

    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between gap-1 mb-2">
          <span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            ${c.category}
          </span>
          <span class="text-[10px] font-mono text-slate-500">Chunk #${c.chunk_index}</span>
        </div>
        <h4 class="font-bold text-sm text-white mb-1">${c.skill_name}</h4>
        <div class="text-[11px] text-sky-400 font-medium mb-2">${c.skill_type || 'Technical Competency'}</div>
        <p class="text-xs text-slate-300 line-clamp-3 mb-3">${c.definition || c.content}</p>
      </div>

      <div class="pt-3 border-t border-slate-900 space-y-2">
        ${relatedBadges ? `
          <div>
            <div class="text-[10px] text-slate-500 mb-1">Related:</div>
            <div class="flex flex-wrap gap-1">${relatedBadges}</div>
          </div>
        ` : ''}
        <div class="flex items-center justify-between text-[10px] text-slate-500">
          <span class="truncate max-w-[150px]">${c.document_filename || 'Standard Doc'}</span>
          <span class="text-emerald-400 font-medium">In SQLite</span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function filterChunksList() {
  const q = document.getElementById('chunkSearchInput').value.toLowerCase().trim();
  if (!q) {
    renderChunksInspector(state.cachedChunks);
    return;
  }
  const filtered = state.cachedChunks.filter(c => 
    (c.skill_name && c.skill_name.toLowerCase().includes(q)) ||
    (c.category && c.category.toLowerCase().includes(q)) ||
    (c.content && c.content.toLowerCase().includes(q))
  );
  renderChunksInspector(filtered);
}

function openUploadModal() {
  document.getElementById('uploadModal').classList.remove('hidden');
}

function closeUploadModal() {
  document.getElementById('uploadModal').classList.add('hidden');
}

function setUploadMode(mode) {
  state.uploadMode = mode;
  const tabFile = document.getElementById('tabFileMode');
  const tabText = document.getElementById('tabTextMode');
  const fileContainer = document.getElementById('fileUploadContainer');
  const textContainer = document.getElementById('textUploadContainer');

  if (mode === 'file') {
    tabFile.className = "flex-1 py-1.5 rounded-lg bg-indigo-600 text-white transition-all";
    tabText.className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition-all";
    fileContainer.classList.remove('hidden');
    textContainer.classList.add('hidden');
  } else {
    tabText.className = "flex-1 py-1.5 rounded-lg bg-indigo-600 text-white transition-all";
    tabFile.className = "flex-1 py-1.5 rounded-lg text-slate-400 hover:text-white transition-all";
    textContainer.classList.remove('hidden');
    fileContainer.classList.add('hidden');
  }
}

function handleFileSelect(input) {
  if (input.files && input.files[0]) {
    state.selectedFile = input.files[0];
    document.getElementById('fileNameDisplay').innerHTML = `
      <span class="text-indigo-400 font-semibold">${state.selectedFile.name}</span>
      <span class="text-slate-400 text-[11px] block mt-0.5">(${Math.round(state.selectedFile.size / 1024)} KB)</span>
    `;
  }
}

async function handleUploadSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById('btnSubmitUpload');
  const framework = document.getElementById('inputFramework').value;

  const formData = new FormData();
  formData.append('framework', framework);

  if (state.uploadMode === 'file') {
    if (!state.selectedFile) {
      showToast('Please select a PDF or file to upload', 'error');
      return;
    }
    formData.append('file', state.selectedFile);
  } else {
    const rawText = document.getElementById('inputRawText').value.trim();
    const title = document.getElementById('inputCustomTitle').value.trim();
    if (!rawText) {
      showToast('Please enter text content', 'error');
      return;
    }
    formData.append('raw_text', rawText);
    formData.append('title', title || 'Custom_Competency');
  }

  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Processing...';
  lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE}/api/admin/upload`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`Success! Ingested ${data.total_chunks} classified chunks into SQLite.`, 'success');
      closeUploadModal();
      document.getElementById('uploadForm').reset();
      document.getElementById('fileNameDisplay').textContent = "Click or drag & drop PDF standard file here";
      state.selectedFile = null;
      refreshAdminData();
    } else {
      showToast(data.detail || 'Upload failed', 'error');
    }
  } catch (err) {
    showToast('Server connection error during upload', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>Process, Classify & Store Chunks</span> <i data-lucide="arrow-right" class="w-4 h-4"></i>';
    lucide.createIcons();
  }
}

async function reprocessAllUploadedFiles() {
  const btn = document.getElementById('btnReprocess');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Re-indexing...';
  lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE}/api/admin/reprocess`, { method: 'POST' });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(data.message, 'success');
      refreshAdminData();
    } else {
      showToast(data.detail || 'Reprocessing failed', 'error');
    }
  } catch (e) {
    showToast('Failed to connect to reprocess service', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="refresh-cw" class="w-4 h-4"></i> <span>Re-index All Uploaded Files</span>';
    lucide.createIcons();
  }
}

async function triggerSeedLoad() {
  const btn = document.getElementById('btnSeedLoad');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Loading...';
  lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE}/api/admin/seed`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message || 'Sample frameworks loaded', data.success ? 'success' : 'info');
    refreshAdminData();
  } catch (e) {
    showToast('Failed to load sample frameworks', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="database" class="w-4 h-4"></i> <span>Load Official Sample Frameworks</span>';
    lucide.createIcons();
  }
}

async function handleDeleteDoc(id) {
  if (!confirm('Are you sure you want to permanently delete this document and all its chunks from SQLite?')) return;
  try {
    const res = await fetch(`${API_BASE}/api/admin/documents/${id}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast('Document removed', 'info');
      refreshAdminData();
    }
  } catch (e) {
    showToast('Error deleting document', 'error');
  }
}

function setQueryPrompt(promptText) {
  const input = document.getElementById('userQueryInput');
  input.value = promptText;
  handleUserSearch(new Event('submit'));
}

async function handleUserSearch(e) {
  if (e) e.preventDefault();
  const input = document.getElementById('userQueryInput');
  const query = input.value.trim();
  if (!query) return;

  const btn = document.getElementById('btnSearch');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Synthesizing...';
  lucide.createIcons();

  try {
    const res = await fetch(`${API_BASE}/api/user/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query })
    });

    if (res.ok) {
      const data = await res.json();
      renderRagResult(data);
      loadQueryHistory();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to query assistant', 'error');
    }
  } catch (err) {
    showToast('Error communicating with RAG server', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>Ask RAG</span> <i data-lucide="sparkles" class="w-3.5 h-3.5"></i>';
    lucide.createIcons();
  }
}

function renderRagResult(data) {
  const resultsArea = document.getElementById('ragResultsArea');
  resultsArea.classList.remove('hidden');

  document.getElementById('ragResultSkillBadge').textContent = data.category || 'General Competency';
  document.getElementById('ragResultFrameworkBadge').textContent = data.framework || 'Occupational Standard';
  document.getElementById('ragResultTitle').textContent = data.skill_name || 'Synthesized Skill Definition';

  const formattedDef = (data.definition || '').replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>');
  document.getElementById('ragResultDefinition').innerHTML = `
    <div class="text-slate-200 text-sm sm:text-base leading-relaxed">
      ${formattedDef}
    </div>
  `;

  document.getElementById('ragResultDifferences').innerHTML = `
    <p class="text-amber-100 text-xs sm:text-sm leading-relaxed">${data.differences || 'No differential analysis available.'}</p>
  `;

  const chipsContainer = document.getElementById('ragRelatedSkillsChips');
  chipsContainer.innerHTML = '';
  if (Array.isArray(data.related_skills) && data.related_skills.length > 0) {
    data.related_skills.forEach(skill => {
      const btn = document.createElement('button');
      btn.onclick = () => setQueryPrompt(`What is ${skill} and how does it differ?`);
      btn.className = 'px-2 py-0.5 rounded-md bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 text-[11px] font-medium border border-amber-500/20 transition-colors';
      btn.textContent = skill;
      chipsContainer.appendChild(btn);
    });
  } else {
    chipsContainer.innerHTML = '<span class="text-slate-500 text-[11px] italic">None specified</span>';
  }

  const sourcesContainer = document.getElementById('ragSourcesList');
  sourcesContainer.innerHTML = '';

  if (!data.sources || data.sources.length === 0) {
    sourcesContainer.innerHTML = '<p class="text-xs text-slate-500 italic">No source chunks directly matched.</p>';
  } else {
    data.sources.forEach(src => {
      const card = document.createElement('div');
      card.className = 'source-card rounded-xl bg-slate-950/70 border border-slate-800/80 p-4 space-y-2';
      card.innerHTML = `
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono">
              Chunk #${src.chunk_index}
            </span>
            <span class="text-xs font-semibold text-white">${src.document_filename}</span>
            <span class="text-[10px] text-slate-400">(${src.framework})</span>
          </div>
          <div class="flex items-center gap-1.5 text-xs text-emerald-400 font-mono">
            <span>Match:</span>
            <span class="font-bold">${src.confidence_score}</span>
          </div>
        </div>
        <div class="text-xs text-slate-300 italic bg-slate-900/40 p-3 rounded-lg border border-slate-800/50">
          "${src.excerpt}"
        </div>
      `;
      sourcesContainer.appendChild(card);
    });
  }

  resultsArea.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  lucide.createIcons();
}

async function loadUserSkillsTaxonomy() {
  const container = document.getElementById('taxonomySkillsList');
  container.innerHTML = '<p class="text-xs text-slate-500 italic">Loading taxonomy from SQLite...</p>';

  try {
    const res = await fetch(`${API_BASE}/api/user/skills`);
    if (res.ok) {
      const skills = await res.json();
      if (!skills || skills.length === 0) {
        container.innerHTML = `<div class="py-6 text-center text-slate-500 text-xs"><p>No skills indexed yet.</p></div>`;
        return;
      }

      const grouped = {};
      skills.forEach(s => {
        if (!grouped[s.category]) grouped[s.category] = [];
        grouped[s.category].push(s);
      });

      container.innerHTML = '';
      for (const [catName, list] of Object.entries(grouped)) {
        const block = document.createElement('div');
        block.className = 'space-y-2';
        
        const badgesHtml = list.map(item => `
          <button 
            onclick="setQueryPrompt('${item.skill_name}')"
            class="px-2.5 py-1 rounded-lg bg-slate-950 hover:bg-indigo-950/60 border border-slate-800 hover:border-indigo-500/40 text-xs text-slate-300 hover:text-indigo-200 transition-all flex items-center gap-1.5"
          >
            <span>${item.skill_name}</span>
          </button>
        `).join('');

        block.innerHTML = `
          <div class="flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
            <h5 class="text-xs font-bold text-slate-300 uppercase tracking-wider">${catName}</h5>
          </div>
          <div class="flex flex-wrap gap-2 pl-3">
            ${badgesHtml}
          </div>
        `;
        container.appendChild(block);
      }
    }
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-slate-500 italic">Could not load skills.</p>';
  }
}

async function loadQueryHistory() {
  const container = document.getElementById('queryHistoryList');
  try {
    const res = await fetch(`${API_BASE}/api/user/history?limit=8`);
    if (res.ok) {
      const history = await res.json();
      if (!history || history.length === 0) {
        container.innerHTML = '<p class="text-xs text-slate-500 italic">No search history yet.</p>';
        return;
      }
      container.innerHTML = '';
      history.forEach(item => {
        const div = document.createElement('div');
        div.className = 'p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 cursor-pointer transition-all';
        div.onclick = () => setQueryPrompt(item.query);
        div.innerHTML = `
          <div class="flex items-center justify-between text-[11px] mb-1">
            <span class="font-semibold text-slate-200 truncate max-w-[190px]">${item.query}</span>
            <span class="text-[10px] text-slate-500">Recent</span>
          </div>
          <div class="text-[11px] text-indigo-400 truncate">${item.skill_identified || 'Grounded definition'}</div>
        `;
        container.appendChild(div);
      });
    }
  } catch (e) {
    container.innerHTML = '<p class="text-xs text-slate-500 italic">Could not fetch history.</p>';
  }
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  const toastIcon = document.getElementById('toastIcon');
  const toastMessage = document.getElementById('toastMessage');

  toastMessage.textContent = message;

  if (type === 'success') {
    toastIcon.innerHTML = '<i data-lucide="check-circle" class="w-4 h-4 text-emerald-400"></i>';
    toast.className = 'fixed bottom-5 right-5 z-50 max-w-sm px-4 py-3 rounded-2xl bg-slate-900 border border-emerald-500/30 shadow-2xl flex items-center gap-3 text-xs text-emerald-200 animate-fade-in';
  } else if (type === 'error') {
    toastIcon.innerHTML = '<i data-lucide="alert-circle" class="w-4 h-4 text-rose-400"></i>';
    toast.className = 'fixed bottom-5 right-5 z-50 max-w-sm px-4 py-3 rounded-2xl bg-slate-900 border border-rose-500/30 shadow-2xl flex items-center gap-3 text-xs text-rose-200 animate-fade-in';
  } else {
    toastIcon.innerHTML = '<i data-lucide="info" class="w-4 h-4 text-sky-400"></i>';
    toast.className = 'fixed bottom-5 right-5 z-50 max-w-sm px-4 py-3 rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl flex items-center gap-3 text-xs text-slate-200 animate-fade-in';
  }

  lucide.createIcons();
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 4000);
}