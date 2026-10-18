let currentJobs = [];
let currentJobIndex = 0;
let approvedJobs = [];
let approvedCount = 0;
let trackedApplications = [];
let activeTab = 'pending';
let selectedResumeVersion = 'tailored'; // 'tailored' or 'standard'
let currentModalTab = 'tailored';

// --- Tab Switching ---
function switchTab(tab) {
    activeTab = tab;
    const tabPending = document.getElementById('tab-pending');
    const tabApproved = document.getElementById('tab-approved');
    const tabTracking = document.getElementById('tab-tracking');
    const tabPosts = document.getElementById('tab-posts');
    const secPending = document.getElementById('pending-section');
    const secApproved = document.getElementById('approved-section');
    const secTracking = document.getElementById('tracking-section');
    const secPosts = document.getElementById('posts-section');

    [tabPending, tabApproved, tabTracking, tabPosts].forEach(t => t && t.classList.remove('active'));
    [secPending, secApproved, secTracking, secPosts].forEach(s => s && s.classList.add('hidden'));

    if (tab === 'pending') {
        if (tabPending) tabPending.classList.add('active');
        if (secPending) secPending.classList.remove('hidden');
        if (currentJobs.length > 0 && currentJobIndex < currentJobs.length) {
            renderJob(currentJobIndex);
        }
    } else if (tab === 'approved') {
        if (tabApproved) tabApproved.classList.add('active');
        if (secApproved) secApproved.classList.remove('hidden');
        fetchApprovedJobs();
    } else if (tab === 'tracking') {
        if (tabTracking) tabTracking.classList.add('active');
        if (secTracking) secTracking.classList.remove('hidden');
        loadAppliedTracking();
    } else if (tab === 'posts') {
        if (tabPosts) tabPosts.classList.add('active');
        if (secPosts) secPosts.classList.remove('hidden');
        loadHiringPosts();
    }
}

// --- Status Badges & Toasts ---
async function updateQueueBadges() {
    const queueCountEl = document.getElementById('queue-count');
    const approvedCountEl = document.getElementById('approved-count');
    const emptyApprovedCountEl = document.getElementById('empty-approved-count');
    const trackingCountEl = document.getElementById('tracking-count');
    const postsCountEl = document.getElementById('posts-count');

    if (queueCountEl) queueCountEl.innerText = currentJobs.length;
    if (approvedCountEl) approvedCountEl.innerText = approvedCount;
    if (emptyApprovedCountEl) emptyApprovedCountEl.innerText = approvedCount;

    if (trackingCountEl) {
        try {
            const resp = await fetch('/api/tracking/applied?limit=1');
            if (resp.ok) {
                const data = await resp.json();
                const total = data.stats?.total_applied ?? (data.total || 0);
                trackingCountEl.innerText = total;
            }
        } catch (e) {
            // Silently ignore badge network failure
        }
    }

    if (postsCountEl) {
        try {
            const resp = await fetch('/api/posts?limit=1');
            if (resp.ok) {
                const data = await resp.json();
                const total = data.stats?.new_leads ?? (data.count || 0);
                postsCountEl.innerText = total;
            }
        } catch (e) {
            // Silently ignore badge network failure
        }
    }
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'reject' ? 'toast-reject' : ''}`;
    toast.innerHTML = type === 'reject'
        ? `<span>✕</span> <span>${message}</span>`
        : `<span>✓</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 2800);
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    fetchJobs();

    document.getElementById('btn-approve').addEventListener('click', approveJob);
    document.getElementById('btn-reject').addEventListener('click', rejectJob);
});

// --- Source Badge Formatting Helper ---
function formatSourceBadge(source, appType) {
    const s = String(source || '').toLowerCase();
    const a = String(appType || '').toUpperCase();

    if (s.includes('linkedin') || a.includes('EASY_APPLY') || a.includes('LINKEDIN')) {
        if (a === 'LINKEDIN_EXTERNAL' || a.includes('EXTERNAL')) {
            return {
                label: '🌐 LinkedIn External',
                cssClass: 'badge-linkedin-ext',
                icon: '🌐'
            };
        }
        return {
            label: '⚡ LinkedIn Easy Apply',
            cssClass: 'badge-linkedin-easy',
            icon: '⚡'
        };
    }
    if (s.includes('greenhouse') || a.includes('GREENHOUSE')) {
        return {
            label: '🟢 Greenhouse ATS',
            cssClass: 'badge-greenhouse',
            icon: '🟢'
        };
    }
    if (s.includes('lever') || a.includes('LEVER')) {
        return {
            label: '🐬 Lever ATS',
            cssClass: 'badge-lever',
            icon: '🐬'
        };
    }
    if (s.includes('ashby') || a.includes('ASHBY')) {
        return {
            label: '🟣 Ashby ATS',
            cssClass: 'badge-ashby',
            icon: '🟣'
        };
    }
    if (s.includes('workday') || a.includes('WORKDAY')) {
        return {
            label: '🟠 Workday ATS',
            cssClass: 'badge-workday',
            icon: '🟠'
        };
    }
    const fallbackText = (source || 'ATS').toUpperCase();
    return {
        label: `💼 ${fallbackText} ATS`,
        cssClass: 'badge-generic-ats',
        icon: '💼'
    };
}

// --- Tab 1: Pending Jobs Logic ---
async function fetchJobs() {
    try {
        const response = await fetch('/api/pending-jobs');
        const data = await response.json();
        currentJobs = data.jobs || [];
        approvedCount = data.approved_count || 0;
        currentJobIndex = 0;
        
        updateQueueBadges();
        document.getElementById('loading').classList.add('hidden');
        
        if (currentJobs.length > 0) {
            renderJob(0);
        } else {
            document.getElementById('job-view').classList.add('hidden');
            document.getElementById('empty-state').classList.remove('hidden');
            // If pending is empty but approved has jobs, automatically show the approved tab!
            if (approvedCount > 0) {
                switchTab('approved');
            }
        }
    } catch (error) {
        console.error('Error fetching pending jobs:', error);
    }
}

function renderJob(index) {
    const job = currentJobs[index];
    if (!job) return;
    
    document.getElementById('job-view').classList.remove('hidden');
    document.getElementById('empty-state').classList.add('hidden');
    
    // Left Col — Job Details
    const jd = job.job_details || {};
    document.getElementById('job-title').innerText = jd.title || 'Untitled';
    document.getElementById('job-company').innerText = jd.company || 'Unknown';

    // Source platform badge
    const badgeInfo = formatSourceBadge(job.source_platform || job.source, job.application_type);
    const sourceEl = document.getElementById('job-source-badge');
    if (sourceEl) {
        sourceEl.innerText = badgeInfo.label;
        sourceEl.className = `section-badge ${badgeInfo.cssClass}`;
    }

    // Dream Org priority badge
    const dreamBadge = document.getElementById('job-dream-badge');
    if (dreamBadge) {
        if (job.is_dream_org) {
            dreamBadge.classList.remove('hidden');
        } else {
            dreamBadge.classList.add('hidden');
        }
    }

    // Staging Referral Button for Dream Orgs
    const referralStagingBtn = document.getElementById('btn-referral-staging');
    if (referralStagingBtn) {
        if (job.is_dream_org) {
            referralStagingBtn.classList.remove('hidden');
        } else {
            referralStagingBtn.classList.add('hidden');
        }
    }

    // Dynamic Location Pill with US / Non-India Warning
    const locInfo = job.location_info || {
        location_text: jd.location || 'Not specified',
        is_us_only: false,
        is_india: false,
        badge_type: 'neutral',
        badge_label: `📍 ${jd.location || 'Not specified'}`
    };
    const locPill = document.getElementById('job-location-pill');
    if (locPill) {
        locPill.className = `location-pill ${locInfo.badge_type || 'neutral'}`;
        locPill.innerText = locInfo.badge_label || `📍 ${locInfo.location_text}`;
    }

    // Meta Matrix Values
    const locVal = document.getElementById('job-location');
    if (locVal) locVal.innerText = locInfo.location_text || jd.location || 'Not specified';

    const expVal = document.getElementById('job-experience');
    if (expVal) expVal.innerText = job.experience_required || 'Not specified';

    const salVal = document.getElementById('job-salary');
    if (salVal) salVal.innerText = job.salary_estimate || jd.salary_range || 'Competitive';

    // Direct Job URL Link Button
    const linkBtn = document.getElementById('job-link-btn');
    const jobUrl = job.direct_link || job.url || job.job_url || '#';
    if (linkBtn) {
        if (jobUrl && jobUrl !== '#') {
            linkBtn.href = jobUrl;
            linkBtn.style.display = 'inline-flex';
            linkBtn.innerText = 'View Live Job ↗';
        } else {
            linkBtn.style.display = 'none';
        }
    }

    // Matched Keywords Tags
    const tagsContainer = document.getElementById('job-matched-tags');
    if (tagsContainer) {
        tagsContainer.innerHTML = '';
        const keywords = job.matched_keywords || [];
        if (keywords.length > 0) {
            keywords.forEach(kw => {
                const span = document.createElement('span');
                span.className = 'keyword-tag';
                span.innerText = kw;
                tagsContainer.appendChild(span);
            });
        } else {
            tagsContainer.innerHTML = '<span class="muted" style="font-size: 0.8rem; font-style: italic;">General QA/SDET match</span>';
        }
    }

    document.getElementById('job-reqs').innerText = jd.requirements || jd.description || 'No requirements provided';
    
    // Reset or preserve resume version for current job
    selectedResumeVersion = job._selected_version || 'tailored';
    updateResumeView();
}

function switchResumeVersion(version) {
    selectedResumeVersion = version;
    const job = currentJobs[currentJobIndex];
    if (job) {
        job._selected_version = version;
    }
    updateResumeView();
}

function updateResumeView() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;

    const toggleTailored = document.getElementById('toggle-tailored');
    const toggleStandard = document.getElementById('toggle-standard');
    const sectionTitle = document.getElementById('achievements-section-title');
    const versionTag = document.getElementById('resume-version-tag');
    const approveBtn = document.getElementById('btn-approve');

    if (selectedResumeVersion === 'standard') {
        if (toggleStandard) toggleStandard.classList.add('active');
        if (toggleTailored) toggleTailored.classList.remove('active');
        if (sectionTitle) sectionTitle.innerText = '📄 Standard Base Achievements';
        if (versionTag) {
            versionTag.innerText = 'Standard Base';
            versionTag.className = 'version-tag standard';
        }
        if (approveBtn) approveBtn.innerText = 'Approve with Standard Base Resume';
    } else {
        if (toggleTailored) toggleTailored.classList.add('active');
        if (toggleStandard) toggleStandard.classList.remove('active');
        if (sectionTitle) sectionTitle.innerText = '✨ Tailored Achievements';
        if (versionTag) {
            versionTag.innerText = 'Tailored';
            versionTag.className = 'version-tag tailored';
        }
        if (approveBtn) approveBtn.innerText = 'Approve with Tailored Resume';
    }

    // Determine which resume data source to render
    const activeResume = (selectedResumeVersion === 'standard')
        ? (job.standard_resume || {})
        : (job.tailored_resume || {});
    
    const pd = activeResume.personal_details || (job.tailored_resume || {}).personal_details || {};
    const candNameEl = document.getElementById('cand-name');
    const candEmailEl = document.getElementById('cand-email');
    if (candNameEl) candNameEl.innerText = pd.full_name || 'Candidate Name';
    if (candEmailEl) candEmailEl.innerText = pd.email || '';

    const expList = document.getElementById('experience-list');
    if (!expList) return;
    expList.innerHTML = '';

    const expHistory = activeResume.experience_history || [];
    if (expHistory.length === 0) {
        expList.innerHTML = `<p style="color: #94a3b8; font-style: italic;">No ${selectedResumeVersion} achievements available.</p>`;
    } else {
        expHistory.forEach(exp => {
            const div = document.createElement('div');
            div.style.marginBottom = '1rem';
            div.innerHTML = `<strong style="color: #60a5fa; font-size: 0.95rem;">${exp.role || ''} @ ${exp.company || ''}</strong><br>`;
            
            if (selectedResumeVersion === 'tailored') {
                const bullets = exp.achievements_diff || (exp.achievements || []).map(a => ({ text: a, is_tailored: false }));
                bullets.forEach(item => {
                    const achText = typeof item === 'string' ? item : item.text;
                    const isTailored = typeof item === 'object' && item.is_tailored;
                    if (isTailored) {
                        div.innerHTML += `<div class="diff-bullet is-tailored"><span class="diff-tag">✨ Tailored</span> ${achText}</div>`;
                    } else {
                        div.innerHTML += `<div class="diff-bullet">• ${achText}</div>`;
                    }
                });
            } else {
                (exp.achievements || []).forEach(ach => {
                    div.innerHTML += `<div class="diff-bullet">• ${ach}</div>`;
                });
            }
            
            div.innerHTML += `<div style="margin-top: 6px;">`;
            (exp.tech_tags || []).forEach(tag => {
                div.innerHTML += `<span class="keyword-tag" style="margin-right: 4px;">${tag}</span>`;
            });
            div.innerHTML += `</div>`;
            expList.appendChild(div);
        });
    }
}

async function approveJob() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;

    const approveBtn = document.getElementById('btn-approve');
    const origText = approveBtn.innerText;
    approveBtn.innerText = 'Approving & Compiling PDF...';
    approveBtn.disabled = true;
    
    // Inject chosen resume version into payload
    const approvalPayload = Object.assign({}, job, {
        resume_choice: selectedResumeVersion || 'tailored'
    });
    
    try {
        const response = await fetch(`/api/approve/${job.job_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(approvalPayload)
        });
        
        if (response.ok) {
            const companyName = job.job_details?.company || 'Company';
            approvedCount++;
            const chosenVer = selectedResumeVersion === 'standard' ? 'Standard Base' : 'Tailored';
            showToast(`Approved with ${chosenVer} PDF for ${companyName}`);
            removeCurrentJobAndAdvance();
        } else {
            const errData = await response.json().catch(() => ({ detail: response.statusText }));
            let message = errData.detail || 'Unknown error occurred.';
            if (typeof message === 'string' && message.includes('validation error')) {
                message = message.replace(/\n\s*For further information visit.*/g, '');
            }
            alert(`Approval Notice:\n\n${message}\n\nPlease check the highlighted fields.`);
        }
    } catch (error) {
        alert(`Network error during approval: ${error.message}`);
    } finally {
        approveBtn.innerText = origText;
        approveBtn.disabled = false;
    }
}

// --- PDF Preview & Comparison Modal Logic ---
function openPdfModal() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;

    const modal = document.getElementById('pdf-modal');
    if (!modal) return;

    const jd = job.job_details || {};
    const headingEl = document.getElementById('modal-heading');
    if (headingEl) {
        headingEl.innerText = `${jd.title || 'Job'} @ ${jd.company || 'Company'}`;
    }

    currentModalTab = selectedResumeVersion || 'tailored';
    modal.classList.remove('hidden');
    switchModalPdfTab(currentModalTab);
}

function closePdfModal() {
    const modal = document.getElementById('pdf-modal');
    const iframe = document.getElementById('pdf-frame');
    if (modal) modal.classList.add('hidden');
    if (iframe) iframe.src = 'about:blank';
}

function handleModalOverlayClick(event) {
    if (event.target && event.target.id === 'pdf-modal') {
        closePdfModal();
    }
}

function switchModalPdfTab(version) {
    currentModalTab = version;
    const tabTailored = document.getElementById('modal-tab-tailored');
    const tabStandard = document.getElementById('modal-tab-standard');
    const iframe = document.getElementById('pdf-frame');
    const selectionLabel = document.getElementById('modal-selection-label');
    const chooseBtn = document.getElementById('btn-modal-choose-version');
    const spinner = document.getElementById('pdf-spinner');
    const extLink = document.getElementById('modal-tab-open-external');

    let pdfUrl = '/api/pdf/standard';
    if (version === 'standard') {
        if (tabStandard) tabStandard.classList.add('active');
        if (tabTailored) tabTailored.classList.remove('active');
        if (selectionLabel) selectionLabel.innerText = '📄 Standard Base Resume';
        if (chooseBtn) chooseBtn.innerText = '✓ Select Standard Base Version';
        pdfUrl = '/api/pdf/standard';
    } else {
        if (tabTailored) tabTailored.classList.add('active');
        if (tabStandard) tabStandard.classList.remove('active');
        if (selectionLabel) selectionLabel.innerText = '✨ Tailored Resume';
        if (chooseBtn) chooseBtn.innerText = '✓ Select Tailored Version';
        const job = currentJobs[currentJobIndex];
        pdfUrl = job ? `/api/pdf/preview/${job.job_id}?version=tailored` : '/api/pdf/standard';
    }

    if (extLink) extLink.href = pdfUrl;

    if (iframe) {
        if (spinner) spinner.classList.remove('hidden');
        iframe.onload = () => {
            if (spinner) spinner.classList.add('hidden');
        };
        // Fallback auto-dismiss in case Chrome's PDF viewer suppresses DOM onload event
        setTimeout(() => {
            if (spinner) spinner.classList.add('hidden');
        }, 1000);

        iframe.src = pdfUrl;
    }
}

function confirmVersionAndClose() {
    switchResumeVersion(currentModalTab);
    closePdfModal();
    const verName = currentModalTab === 'standard' ? 'Standard Base' : 'Tailored';
    showToast(`Active selection updated to ${verName} Resume`);
}

async function rejectJob() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;
    try {
        const response = await fetch(`/api/reject/${job.job_id}`, { method: 'POST' });
        if (response.ok) {
            const companyName = job.job_details?.company || 'Job';
            showToast(`Skipped ${companyName}`, 'reject');
            removeCurrentJobAndAdvance();
        }
    } catch (error) {
        console.error('Rejection failed:', error);
    }
}

function removeCurrentJobAndAdvance() {
    if (currentJobs.length === 0) return;
    currentJobs.splice(currentJobIndex, 1);
    updateQueueBadges();
    
    if (currentJobs.length === 0) {
        document.getElementById('job-view').classList.add('hidden');
        document.getElementById('empty-state').classList.remove('hidden');
    } else {
        if (currentJobIndex >= currentJobs.length) {
            currentJobIndex = 0;
        }
        renderJob(currentJobIndex);
    }
}

// --- TAB 2: Ready to Apply Command Center ---
async function fetchApprovedJobs() {
    const listContainer = document.getElementById('approved-jobs-list');
    const loadingEl = document.getElementById('approved-loading');
    const emptyEl = document.getElementById('approved-empty-state');

    loadingEl.classList.remove('hidden');
    listContainer.innerHTML = '';
    emptyEl.classList.add('hidden');

    try {
        const response = await fetch('/api/approved-jobs');
        const data = await response.json();
        approvedJobs = data.jobs || [];
        approvedCount = data.total_approved || approvedJobs.length;

        // Update budget banner
        const budget = data.budget || {};
        document.getElementById('budget-used').innerText = budget.current_count || budget.used_today || 0;
        document.getElementById('budget-max').innerText = budget.daily_limit || 200;

        updateQueueBadges();
        loadingEl.classList.add('hidden');

        if (approvedJobs.length === 0) {
            emptyEl.classList.remove('hidden');
        } else {
            renderApprovedGrid(approvedJobs);
        }
    } catch (error) {
        console.error('Error fetching approved jobs:', error);
        loadingEl.classList.add('hidden');
    }
}

function renderApprovedGrid(jobs) {
    const listContainer = document.getElementById('approved-jobs-list');
    const emptyEl = document.getElementById('approved-empty-state');
    listContainer.innerHTML = '';

    if (!jobs || jobs.length === 0) {
        emptyEl.classList.remove('hidden');
        return;
    }
    emptyEl.classList.add('hidden');

    jobs.forEach(job => {
        const card = document.createElement('div');
        card.className = 'approved-card';
        card.id = `approved-card-${job.job_id}`;

        const badgeInfo = formatSourceBadge(job.source, job.application_type);
        const dreamHtml = job.is_dream_org ? '<span class="dream-pill">⭐ Dream Org</span>' : '';

        const keywordsHtml = (job.matched_keywords || []).slice(0, 4)
            .map(k => `<span class="keyword-tag">${k}</span>`).join('');

        const referralBtnHtml = job.is_dream_org
            ? `<button class="btn-referral" onclick="openReferralModal('${job.job_id}')" title="Generate targeted LinkedIn referral note for Engineering Manager">🤝 Referral Note</button>`
            : '';

        card.innerHTML = `
            <div>
                <div class="card-top">
                    <div class="company-title">
                        <h3>${job.company}</h3>
                        <p>${job.title}</p>
                    </div>
                    <div class="badge-cluster">
                        ${dreamHtml}
                        <span class="source-pill ${badgeInfo.cssClass}">${badgeInfo.label}</span>
                    </div>
                </div>
                <div class="card-meta">
                    <span>📍 ${job.location || 'Remote'}</span>
                    <span>📑 ATS PDF Ready</span>
                </div>
                <div class="tags-row">
                    ${keywordsHtml}
                </div>
            </div>
            <div class="card-footer">
                <div class="footer-left">
                    <a href="/api/pdf/${job.job_id}" target="_blank" class="btn-pdf">
                        📄 View PDF
                    </a>
                    ${referralBtnHtml}
                    <button class="btn-copilot" onclick="autofillApprovedJob('${job.job_id}', this)">
                        🚀 Launch Copilot
                    </button>
                    <button class="btn-manual" onclick="manualApplyApprovedJob('${job.job_id}', this)" title="Open in Chrome with Candidate Cheat Sheet">
                        🖐️ Manual Apply
                    </button>
                    <button class="btn-mark-applied" onclick="markApprovedJobApplied('${job.job_id}', this)" title="Mark as applied and move to tracking">
                        ✅ Applied
                    </button>
                </div>
                <button class="btn-discard" title="Discard from approved" onclick="discardApprovedJob('${job.job_id}', this)">
                    ✕
                </button>
            </div>
        `;
        listContainer.appendChild(card);
    });
}

function filterApprovedJobs() {
    const query = document.getElementById('approved-search').value.toLowerCase().trim();
    if (!query) {
        renderApprovedGrid(approvedJobs);
        return;
    }
    const filtered = approvedJobs.filter(job => {
        const companyMatch = (job.company || '').toLowerCase().includes(query);
        const titleMatch = (job.title || '').toLowerCase().includes(query);
        const kwMatch = (job.matched_keywords || []).some(k => k.toLowerCase().includes(query));
        const badgeInfo = formatSourceBadge(job.source, job.application_type);
        const sourceMatch = (job.source || '').toLowerCase().includes(query) || badgeInfo.label.toLowerCase().includes(query);
        return companyMatch || titleMatch || kwMatch || sourceMatch;
    });
    renderApprovedGrid(filtered);
}

async function autofillApprovedJob(jobId, btnElement) {
    const job = approvedJobs.find(j => j.job_id === jobId);
    if (job && job.is_dream_org) {
        showDreamAdvisoryModal(jobId, () => executeAutofillApprovedJob(jobId, btnElement));
        return;
    }
    await executeAutofillApprovedJob(jobId, btnElement);
}

async function executeAutofillApprovedJob(jobId, btnElement) {
    const origText = btnElement.innerText;
    btnElement.innerText = '⏳ Launching...';
    btnElement.disabled = true;

    try {
        const response = await fetch(`/api/autofill/${jobId}`, { method: 'POST' });
        const res = await response.json();
        
        if (response.ok) {
            showToast(`Stealth Browser launched! Form pre-filled & paused for your review.`);
            // Update budget
            const usedEl = document.getElementById('budget-used');
            if (usedEl) {
                const currentUsed = parseInt(usedEl.innerText, 10) || 0;
                usedEl.innerText = currentUsed + 1;
            }
        } else {
            alert(`Autofill Notice:\n\n${res.detail || response.statusText}`);
        }
    } catch (e) {
        console.error('Autofill error:', e);
        alert('Autofill network error: ' + e.message);
    } finally {
        btnElement.innerText = origText;
        btnElement.disabled = false;
    }
}

async function manualApplyApprovedJob(jobId, btnElement) {
    const origText = btnElement.innerText;
    btnElement.innerText = '⏳ Opening...';
    btnElement.disabled = true;

    try {
        const response = await fetch(`/api/autofill/manual/${jobId}`, { method: 'POST' });
        const res = await response.json();
        
        if (response.ok) {
            showToast(`Headful Chrome launched with Candidate Cheat Sheet!`);
            const usedEl = document.getElementById('budget-used');
            if (usedEl) {
                const currentUsed = parseInt(usedEl.innerText, 10) || 0;
                usedEl.innerText = currentUsed + 1;
            }
        } else {
            alert(`Manual Apply Notice:\n\n${res.detail || response.statusText}`);
        }
    } catch (e) {
        console.error('Manual apply error:', e);
        alert('Manual apply network error: ' + e.message);
    } finally {
        btnElement.innerText = origText;
        btnElement.disabled = false;
    }
}

async function manualApplyCurrentStagingJob() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;
    const btn = document.getElementById('btn-manual-staging');
    if (btn) {
        btn.innerText = '⏳ Opening...';
        btn.disabled = true;
    }
    try {
        const response = await fetch(`/api/autofill/manual/${job.job_id}`, { method: 'POST' });
        const res = await response.json();
        if (response.ok) {
            showToast(`Headful Chrome launched with Candidate Cheat Sheet!`);
            const usedEl = document.getElementById('budget-used');
            if (usedEl) {
                const currentUsed = parseInt(usedEl.innerText, 10) || 0;
                usedEl.innerText = currentUsed + 1;
            }
        } else {
            alert(`Manual Apply Notice:\n\n${res.detail || response.statusText}`);
        }
    } catch (e) {
        console.error('Manual apply error:', e);
        alert('Manual apply network error: ' + e.message);
    } finally {
        if (btn) {
            btn.innerText = '🖐️ Manual Apply';
            btn.disabled = false;
        }
    }
}

async function discardApprovedJob(jobId, btnElement) {
    if (!confirm('Remove this application from your approved queue?')) return;

    try {
        const response = await fetch(`/api/approved/${jobId}`, { method: 'DELETE' });
        if (response.ok) {
            approvedJobs = approvedJobs.filter(j => j.job_id !== jobId);
            approvedCount = approvedJobs.length;
            updateQueueBadges();
            
            const card = document.getElementById(`approved-card-${jobId}`);
            if (card) {
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => card.remove(), 250);
            }
            showToast('Job removed from approved queue', 'reject');
        } else {
            alert('Failed to remove job.');
        }
    } catch (e) {
        console.error('Error discarding job:', e);
    }
}

async function batchApplyNext() {
    if (approvedJobs.length === 0) {
        alert('No approved jobs available to apply.');
        return;
    }

    const nextJob = approvedJobs[0];
    const card = document.getElementById(`approved-card-${nextJob.job_id}`);
    const btn = card ? card.querySelector('.btn-copilot') : null;

    if (confirm(`Launch assisted copilot for next job: ${nextJob.title} @ ${nextJob.company}?`)) {
        if (btn) {
            autofillApprovedJob(nextJob.job_id, btn);
        } else {
            const fakeBtn = document.createElement('button');
            autofillApprovedJob(nextJob.job_id, fakeBtn);
        }
    }
}

// --- TAB 3: APPLIED TRACKING DASHBOARD LOGIC ---

async function markCurrentJobApplied() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;

    const companyName = job.job_details?.company || 'Company';
    const jobTitle = job.job_details?.title || 'this role';
    const confirmed = confirm(`Confirm Submission:\n\nHave you submitted your application for ${jobTitle} @ ${companyName}?\n\nClick OK to record as applied and move to tracking.`);
    if (!confirmed) return;

    const btn = document.getElementById('btn-mark-applied-staging');
    const origText = btn ? btn.innerText : '';
    if (btn) {
        btn.innerText = '⏳ Saving...';
        btn.disabled = true;
    }

    try {
        const response = await fetch(`/api/tracking/mark-applied/${job.job_id}`, {
            method: 'POST'
        });
        const data = await response.json();
        if (response.ok) {
            showToast(`✅ Marked as Applied: ${companyName}`);
            removeCurrentJobAndAdvance();
            updateQueueBadges();
        } else {
            alert(`Could not mark as applied:\n\n${data.detail || response.statusText}`);
        }
    } catch (err) {
        console.error('Error marking staging job applied:', err);
        alert(`Network error marking job applied: ${err.message}`);
    } finally {
        if (btn) {
            btn.innerText = origText;
            btn.disabled = false;
        }
    }
}

async function markApprovedJobApplied(jobId, btnElement) {
    const job = approvedJobs.find(j => j.job_id === jobId);
    const companyName = job ? job.company : 'Company';
    const jobTitle = job ? job.title : 'this role';

    const confirmed = confirm(`Confirm Submission:\n\nHave you submitted your application for ${jobTitle} @ ${companyName}?\n\nClick OK to record as applied and move to tracking.`);
    if (!confirmed) return;

    const origText = btnElement ? btnElement.innerText : '';
    if (btnElement) {
        btnElement.innerText = '⏳ Saving...';
        btnElement.disabled = true;
    }

    try {
        const response = await fetch(`/api/tracking/mark-applied/${jobId}`, {
            method: 'POST'
        });
        const data = await response.json();
        if (response.ok) {
            showToast(`✅ Saved to Applied Tracking: ${companyName}`);

            const card = document.getElementById(`approved-card-${jobId}`);
            if (card) {
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => card.remove(), 250);
            }
            approvedJobs = approvedJobs.filter(j => j.job_id !== jobId);
            approvedCount = approvedJobs.length;
            updateQueueBadges();

            if (approvedJobs.length === 0) {
                const emptyEl = document.getElementById('approved-empty-state');
                if (emptyEl) emptyEl.classList.remove('hidden');
            }
        } else {
            alert(`Could not mark as applied:\n\n${data.detail || response.statusText}`);
        }
    } catch (err) {
        console.error('Error marking approved job applied:', err);
        alert(`Network error: ${err.message}`);
    } finally {
        if (btnElement) {
            btnElement.innerText = origText;
            btnElement.disabled = false;
        }
    }
}

async function loadAppliedTracking() {
    const loadingEl = document.getElementById('tracking-loading');
    const listContainer = document.getElementById('tracking-jobs-list');
    const emptyEl = document.getElementById('tracking-empty-state');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (listContainer) listContainer.innerHTML = '';
    if (emptyEl) emptyEl.classList.add('hidden');

    try {
        const response = await fetch('/api/tracking/applied');
        const data = await response.json();
        trackedApplications = data.applications || [];

        // Update KPIs
        const stats = data.stats || {};
        const kpiTotal = document.getElementById('kpi-total-applied');
        const kpiToday = document.getElementById('kpi-today-applied');
        const kpiPlatforms = document.getElementById('kpi-platforms-count');
        const badgeCount = document.getElementById('tracking-count');

        if (kpiTotal) kpiTotal.innerText = stats.total_applied || trackedApplications.length;
        if (kpiToday) kpiToday.innerText = stats.applied_today || 0;
        if (kpiPlatforms) {
            const sources = Object.keys(stats.source_breakdown || {});
            kpiPlatforms.innerText = sources.length || (trackedApplications.length > 0 ? 1 : 0);
        }
        if (badgeCount) badgeCount.innerText = stats.total_applied || trackedApplications.length;

        if (loadingEl) loadingEl.classList.add('hidden');

        if (trackedApplications.length === 0) {
            if (emptyEl) emptyEl.classList.remove('hidden');
        } else {
            renderTrackingGrid(trackedApplications);
        }
    } catch (error) {
        console.error('Error fetching applied tracking:', error);
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function renderTrackingGrid(apps) {
    const listContainer = document.getElementById('tracking-jobs-list');
    const emptyEl = document.getElementById('tracking-empty-state');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    if (!apps || apps.length === 0) {
        if (emptyEl) emptyEl.classList.remove('hidden');
        return;
    }
    if (emptyEl) emptyEl.classList.add('hidden');

    apps.forEach(app => {
        const card = document.createElement('div');
        card.className = 'tracking-card';
        card.id = `tracking-card-${app.job_id}`;

        const badgeInfo = formatSourceBadge(app.source, app.application_type);

        // Format applied timestamp
        let formattedDate = 'Recently';
        if (app.applied_at) {
            try {
                const d = new Date(app.applied_at);
                formattedDate = d.toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            } catch (e) {
                formattedDate = app.applied_at;
            }
        }

        const statusClass = (app.status || 'applied').toLowerCase().includes('interview')
            ? 'interview'
            : (app.status || 'applied').toLowerCase().includes('submitted')
                ? 'submitted'
                : 'applied';

        const statusDisplay = (app.status || 'Applied').replace(/_/g, ' ').toUpperCase();
        const hasPdf = Boolean(app.resume_path);
        const jobUrl = app.job_url || '#';
        const dreamHtml = app.is_dream_org ? '<span class="dream-pill">⭐ Dream Org</span>' : '';

        card.innerHTML = `
            <div>
                <div class="tracking-card-header">
                    <div class="tracking-company-title">
                        <h3>${app.company_name || 'Unknown Company'}</h3>
                        <p>${app.job_title || 'Software Engineer'}</p>
                    </div>
                    <div class="tracking-badge-group">
                        ${dreamHtml}
                        <span class="source-pill ${badgeInfo.cssClass}">${badgeInfo.label}</span>
                        <span class="status-pill ${statusClass}">${statusDisplay}</span>
                    </div>
                </div>
                <div class="tracking-meta">
                    <span>🕒 Applied: <strong>${formattedDate}</strong></span>
                    <span>🆔 ID: <code>${app.job_id}</code></span>
                </div>
            </div>
            <div class="tracking-footer">
                <div class="tracking-footer-actions">
                    <a href="/api/pdf/${app.job_id}" target="_blank" class="btn-pdf" ${hasPdf ? '' : 'style="display:none;"'}>
                        📄 View Tailored PDF
                    </a>
                    ${jobUrl && jobUrl !== '#' ? `<a href="${jobUrl}" target="_blank" class="btn-secondary-sm" style="text-decoration:none; display:inline-flex; align-items:center; gap:4px;">🔗 Job Posting ↗</a>` : ''}
                </div>
                <button class="btn-discard" title="Delete from tracking archive" onclick="deleteTrackedApplication('${app.job_id}', this)">
                    🗑️
                </button>
            </div>
        `;
        listContainer.appendChild(card);
    });
}

function filterTrackingJobs() {
    const input = document.getElementById('tracking-search');
    if (!input) return;
    const query = input.value.toLowerCase().trim();
    if (!query) {
        renderTrackingGrid(trackedApplications);
        return;
    }
    const filtered = trackedApplications.filter(app => {
        const comp = (app.company_name || '').toLowerCase().includes(query);
        const title = (app.job_title || '').toLowerCase().includes(query);
        const badgeInfo = formatSourceBadge(app.source, app.application_type);
        const src = (app.source || '').toLowerCase().includes(query) || badgeInfo.label.toLowerCase().includes(query);
        const status = (app.status || '').toLowerCase().includes(query);
        const jobId = (app.job_id || '').toLowerCase().includes(query);
        return comp || title || src || status || jobId;
    });
    renderTrackingGrid(filtered);
}

async function deleteTrackedApplication(jobId, btnElement) {
    if (!confirm(`Remove application #${jobId} from tracking archive?`)) return;

    try {
        const response = await fetch(`/api/tracking/${jobId}`, { method: 'DELETE' });
        if (response.ok) {
            trackedApplications = trackedApplications.filter(a => a.job_id !== jobId);
            const card = document.getElementById(`tracking-card-${jobId}`);
            if (card) {
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => card.remove(), 250);
            }
            showToast('Application removed from tracking archive');
            updateQueueBadges();
            const kpiTotal = document.getElementById('kpi-total-applied');
            if (kpiTotal) kpiTotal.innerText = trackedApplications.length;
            if (trackedApplications.length === 0) {
                const emptyEl = document.getElementById('tracking-empty-state');
                if (emptyEl) emptyEl.classList.remove('hidden');
            }
        } else {
            alert('Failed to remove application.');
        }
    } catch (e) {
        console.error('Error deleting tracked application:', e);
    }
}

// --- SPRINT 3: Referral Reconnaissance & Dual-Funnel Routing ---
let currentReferralPack = null;
let currentReferralFormat = 'connection';
let currentReferralJobId = null;
let pendingColdApplyCallback = null;

function openReferralModalCurrentJob() {
    const job = currentJobs[currentJobIndex];
    if (!job) return;
    openReferralModal(job.job_id);
}

async function openReferralModal(jobId) {
    currentReferralJobId = jobId;
    currentReferralFormat = 'connection';
    const modal = document.getElementById('referral-modal');
    if (!modal) return;
    modal.classList.remove('hidden');

    const statusEl = document.getElementById('referral-log-status');
    const textarea = document.getElementById('referral-note-text');
    const recipientInput = document.getElementById('referral-recipient-input');

    if (recipientInput) recipientInput.value = '';
    if (statusEl) statusEl.innerText = 'Fetching live reconnaissance pack...';
    if (textarea) textarea.value = 'Generating tailored referral note...';

    await fetchAndRenderReferralPack(jobId, 'there');
}

async function fetchAndRenderReferralPack(jobId, recipientName) {
    try {
        const response = await fetch(`/api/referral/generate/${jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ recipient_name: recipientName })
        });
        const data = await response.json();
        if (response.ok && data.referral_pack) {
            currentReferralPack = data.referral_pack;
            renderReferralModalData();
        } else {
            alert(`Referral Error: ${data.detail || 'Could not generate pack'}`);
            closeReferralModal();
        }
    } catch (e) {
        console.error('Error fetching referral pack:', e);
        alert('Network error generating referral pack.');
    }
}

function renderReferralModalData() {
    if (!currentReferralPack) return;
    const p = currentReferralPack;

    const heading = document.getElementById('referral-modal-heading');
    if (heading) heading.innerText = `Referral Pitch: ${p.company_name}`;

    const subtitle = document.getElementById('referral-job-subtitle');
    if (subtitle) {
        const jobUrlHtml = p.job_url ? ` • <a href="${p.job_url}" target="_blank" style="color:#60a5fa;text-decoration:underline;">View Job ↗</a>` : '';
        subtitle.innerHTML = `${p.company_name} • ${p.job_title} (Req ID: ${p.requisition_id || 'N/A'})${jobUrlHtml}`;
    }

    // Populate search links
    const urls = p.search_urls || {};
    const linkEm = document.getElementById('link-search-em');
    if (linkEm && urls.engineering_managers) linkEm.href = urls.engineering_managers;

    const linkQa = document.getElementById('link-search-qa');
    if (linkQa && urls.qa_leads) linkQa.href = urls.qa_leads;

    const linkAlumni = document.getElementById('link-search-alumni');
    if (linkAlumni && urls.alumni) linkAlumni.href = urls.alumni;

    // Populate character count badges
    const connCount = document.getElementById('conn-char-count');
    if (connCount) connCount.innerText = `${p.connection_note_chars}/300`;

    const inmailCount = document.getElementById('inmail-char-count');
    if (inmailCount) inmailCount.innerText = `${p.inmail_pitch_chars}/1000`;

    updateActiveReferralNoteText();
    const statusEl = document.getElementById('referral-log-status');
    if (statusEl) statusEl.innerText = 'Ready to copy and connect';
}

function switchReferralFormat(format) {
    currentReferralFormat = format;
    const tabConn = document.getElementById('tab-format-conn');
    const tabInmail = document.getElementById('tab-format-inmail');

    if (format === 'connection') {
        if (tabConn) tabConn.classList.add('active');
        if (tabInmail) tabInmail.classList.remove('active');
    } else {
        if (tabConn) tabConn.classList.remove('active');
        if (tabInmail) tabInmail.classList.add('active');
    }
    updateActiveReferralNoteText();
}

function updateActiveReferralNoteText() {
    if (!currentReferralPack) return;
    const textarea = document.getElementById('referral-note-text');
    const charIndicator = document.getElementById('char-limit-indicator');
    if (!textarea) return;

    if (currentReferralFormat === 'connection') {
        textarea.value = currentReferralPack.connection_note;
        if (charIndicator) {
            charIndicator.innerText = `LinkedIn Connection Note: ${currentReferralPack.connection_note_chars} / 300 characters`;
            charIndicator.style.color = currentReferralPack.connection_note_chars <= 300 ? '#34d399' : '#f87171';
        }
    } else {
        textarea.value = currentReferralPack.inmail_pitch;
        if (charIndicator) {
            charIndicator.innerText = `LinkedIn InMail Message: ${currentReferralPack.inmail_pitch_chars} / 1000 characters`;
            charIndicator.style.color = currentReferralPack.inmail_pitch_chars <= 1000 ? '#34d399' : '#f87171';
        }
    }
}

let recipientDebounceTimer = null;
function updateReferralRecipient(val) {
    clearTimeout(recipientDebounceTimer);
    recipientDebounceTimer = setTimeout(() => {
        if (currentReferralJobId) {
            fetchAndRenderReferralPack(currentReferralJobId, val || 'there');
        }
    }, 350);
}

function copyReferralNote() {
    const textarea = document.getElementById('referral-note-text');
    if (!textarea || !textarea.value) return;
    navigator.clipboard.writeText(textarea.value).then(() => {
        showToast('Referral note copied to clipboard!');
        const statusEl = document.getElementById('referral-log-status');
        if (statusEl) statusEl.innerText = 'Copied to clipboard ✓';
    }).catch(err => {
        console.error('Clipboard copy failed:', err);
        textarea.select();
        document.execCommand('copy');
        showToast('Copied to clipboard!');
    });
}

async function logReferralOutreachToDb() {
    if (!currentReferralPack || !currentReferralJobId) return;
    const recipientInput = document.getElementById('referral-recipient-input');
    const contactName = recipientInput ? recipientInput.value.trim() : '';

    const payload = {
        job_id: currentReferralJobId,
        company_name: currentReferralPack.company_name,
        job_title: currentReferralPack.job_title,
        requisition_id: currentReferralPack.requisition_id,
        outreach_type: currentReferralFormat === 'connection' ? 'connection_note' : 'inmail',
        note_content: document.getElementById('referral-note-text').value,
        contact_name: contactName || null,
        status: 'SENT'
    };

    try {
        const response = await fetch('/api/referral/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (response.ok) {
            showToast('Outreach logged to SQLite tracking ledger ✓');
            const statusEl = document.getElementById('referral-log-status');
            if (statusEl) statusEl.innerText = 'Logged as SENT in SQLite ✓';
        } else {
            showToast('Failed to log outreach to database', 'reject');
        }
    } catch (e) {
        console.error('Error logging referral outreach:', e);
    }
}

function closeReferralModal() {
    const modal = document.getElementById('referral-modal');
    if (modal) modal.classList.add('hidden');
    currentReferralPack = null;
    currentReferralJobId = null;
}

function handleReferralModalOverlayClick(e) {
    if (e.target.id === 'referral-modal') {
        closeReferralModal();
    }
}

// --- Dream Org Advisory Modal ---
function showDreamAdvisoryModal(jobId, onOverride) {
    pendingColdApplyCallback = onOverride;
    currentReferralJobId = jobId;
    const modal = document.getElementById('dream-advisory-modal');
    if (modal) modal.classList.remove('hidden');
}

function closeDreamAdvisoryModal() {
    const modal = document.getElementById('dream-advisory-modal');
    if (modal) modal.classList.add('hidden');
    pendingColdApplyCallback = null;
}

function handleDreamAdvisoryOverlayClick(e) {
    if (e.target.id === 'dream-advisory-modal') {
        closeDreamAdvisoryModal();
    }
}

function proceedToReferralFromAdvisory() {
    const jId = currentReferralJobId;
    closeDreamAdvisoryModal();
    if (jId) {
        openReferralModal(jId);
    }
}

function confirmColdApplyOverride() {
    const cb = pendingColdApplyCallback;
    closeDreamAdvisoryModal();
    if (cb && typeof cb === 'function') {
        cb();
    }
}

// ==============================================================================
// Track 3: Recruiter, Lead & Peer Hiring Posts UI Controller
// ==============================================================================

// Helper: XSS-safe HTML Escaping
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Helper: Resilient Clipboard Copy
function copyTextToClipboard(text, msg = 'Copied to clipboard!') {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(msg);
        }).catch(() => {
            fallbackCopyText(text, msg);
        });
    } else {
        fallbackCopyText(text, msg);
    }
}

function fallbackCopyText(text, msg) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showToast(msg);
    } catch (e) {
        showToast('Failed to copy', 'error');
    }
    document.body.removeChild(ta);
}

let currentPosts = [];
let currentPostFilter = 'all';
let currentActivePost = null;

async function loadHiringPosts() {
    const loadingEl = document.getElementById('posts-loading');
    const gridEl = document.getElementById('posts-grid');
    const emptyEl = document.getElementById('posts-empty-state');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (gridEl) gridEl.innerHTML = '';
    if (emptyEl) emptyEl.classList.add('hidden');

    try {
        const resp = await fetch('/api/posts?limit=100');
        if (!resp.ok) throw new Error(`HTTP error ${resp.status}`);
        const data = await resp.json();

        currentPosts = data.posts || [];
        updatePostKpis(data.stats || {});
        updateQueueBadges();

        if (loadingEl) loadingEl.classList.add('hidden');

        if (currentPosts.length === 0) {
            if (emptyEl) emptyEl.classList.remove('hidden');
        } else {
            renderHiringPosts(currentPosts);
        }
    } catch (e) {
        if (loadingEl) loadingEl.classList.add('hidden');
        showToast(`Failed to load hiring posts: ${e.message}`, 'error');
    }
}

function updatePostKpis(stats) {
    const totalEl = document.getElementById('kpi-total-posts');
    const dreamEl = document.getElementById('kpi-dream-posts');
    const freshEl = document.getElementById('kpi-fresh-posts');
    const emailEl = document.getElementById('kpi-email-posts');
    const contactedEl = document.getElementById('kpi-contacted-posts');

    if (totalEl) totalEl.innerText = stats.total_posts || 0;
    if (dreamEl) dreamEl.innerText = stats.dream_orgs || 0;
    if (freshEl) freshEl.innerText = stats.fresh_24h || 0;
    if (emailEl) emailEl.innerText = stats.has_email || 0;
    if (contactedEl) contactedEl.innerText = stats.contacted || 0;
}

function renderHiringPosts(posts) {
    const gridEl = document.getElementById('posts-grid');
    const emptyEl = document.getElementById('posts-empty-state');
    if (!gridEl) return;

    gridEl.innerHTML = '';

    if (!posts || posts.length === 0) {
        if (emptyEl) emptyEl.classList.remove('hidden');
        return;
    }
    if (emptyEl) emptyEl.classList.add('hidden');

    posts.forEach(post => {
        const card = createPostCardElement(post);
        gridEl.appendChild(card);
    });
}

function createPostCardElement(post) {
    const card = document.createElement('div');
    card.className = 'post-card glass-panel';
    card.id = `post-card-${post.post_id}`;

    // Role category badge configuration
    let roleBadge = '🛡️ Engineer';
    let roleClass = 'role-engineer';
    if (post.author_role_category === 'RECRUITER') {
        roleBadge = '🎯 Recruiter';
        roleClass = 'role-recruiter';
    } else if (post.author_role_category === 'LEADER') {
        roleBadge = '👔 Lead / EM';
        roleClass = 'role-leader';
    } else if (post.author_role_category === 'PEER') {
        roleBadge = '👥 Team Peer';
        roleClass = 'role-peer';
    }

    const dreamPill = post.is_dream_org ? '<span class="dream-pill">⭐ Dream Org</span>' : '';
    const statusPill = post.outreach_status === 'DM_SENT' || post.outreach_status === 'CONTACTED'
        ? '<span class="badge badge-success">✓ Contacted</span>'
        : post.outreach_status === 'DISMISSED'
        ? '<span class="badge badge-secondary">Dismissed</span>'
        : '<span class="badge badge-warning">⚡ New Lead</span>';

    // Emails and Links pills
    let actionPillsHtml = '';
    if (post.extracted_emails && post.extracted_emails.length > 0) {
        post.extracted_emails.forEach(email => {
            actionPillsHtml += `<button class="pill-action pill-email" onclick="copyTextToClipboard('${email}', 'Email copied!')" title="Click to copy email">✉️ ${email}</button>`;
        });
    }

    if (post.extracted_job_codes && post.extracted_job_codes.length > 0) {
        post.extracted_job_codes.forEach(code => {
            actionPillsHtml += `<span class="pill-action pill-code">🆔 ${code}</span>`;
        });
    }

    if (post.extracted_links && post.extracted_links.length > 0) {
        post.extracted_links.slice(0, 2).forEach(link => {
            const domain = link.replace(/https?:\/\/(www\.)?/, '').split('/')[0];
            actionPillsHtml += `<a href="${link}" target="_blank" class="pill-action pill-link" title="Open Link">🔗 ${domain} ↗</a>`;
        });
    }

    // Snippet with see more toggle
    const textSnippet = escapeHtml(post.post_text || '');
    const cleanSnippet = textSnippet.length > 320
        ? `${textSnippet.substring(0, 320)}... <span class="snippet-expand" onclick="togglePostSnippet('${post.post_id}')">Read more</span>`
        : textSnippet;

    let postLinkUrl = post.post_url;
    if (postLinkUrl && /\/feed\/update\/[0-9a-f]{8,32}\/?$/i.test(postLinkUrl)) {
        if (post.author_profile_url) {
            postLinkUrl = post.author_profile_url.includes('/company/')
                ? `${post.author_profile_url.replace(/\/+$/, '')}/posts/`
                : `${post.author_profile_url.replace(/\/+$/, '')}/recent-activity/all/`;
        }
    }
    const isFeedOrActivity = postLinkUrl && (postLinkUrl.includes('/recent-activity/') || postLinkUrl.endsWith('/posts/'));
    const postLinkLabel = isFeedOrActivity ? '🔗 View Author Posts ↗' : '🔗 View LinkedIn Post ↗';

    card.innerHTML = `
        <div class="post-card-header">
            <div class="post-author-box">
                <div class="author-avatar">${(post.author_name || 'U')[0].toUpperCase()}</div>
                <div class="author-info">
                    <div class="author-name-row">
                        <span class="author-name">${escapeHtml(post.author_name || 'LinkedIn User')}</span>
                        <span class="author-role-badge ${roleClass}">${roleBadge}</span>
                        ${dreamPill}
                    </div>
                    <div class="author-headline">${escapeHtml(post.author_headline || '')}</div>
                </div>
            </div>
            <div class="post-meta-badges">
                <span class="post-age-badge">🕒 ${post.posted_at_relative || 'Recently'}</span>
                ${statusPill}
            </div>
        </div>

        ${actionPillsHtml ? `<div class="post-action-pills">${actionPillsHtml}</div>` : ''}

        <div class="post-snippet-box" id="post-snippet-${post.post_id}">
            <p class="post-text">${cleanSnippet}</p>
            <p class="post-full-text hidden">${textSnippet} <span class="snippet-expand" onclick="togglePostSnippet('${post.post_id}')">Show less</span></p>
        </div>

        <div class="post-card-footer">
            <div class="post-links-row">
                ${postLinkUrl ? `<a href="${postLinkUrl}" target="_blank" class="post-external-link">${postLinkLabel}</a>` : ''}
                ${post.author_profile_url ? `<a href="${post.author_profile_url}" target="_blank" class="post-external-link">👤 Author Profile ↗</a>` : ''}
            </div>
            <div class="post-action-buttons">
                <button class="btn btn-accent-sm" onclick="openPostOutreachModal('${post.post_id}')">
                    💬 Draft Outreach
                </button>
                <button class="btn btn-secondary-sm" onclick="markPostContacted('${post.post_id}')" title="Mark as Contacted">
                    ✓
                </button>
                <button class="btn btn-secondary-sm" onclick="dismissPost('${post.post_id}')" title="Dismiss Post">
                    ✕
                </button>
            </div>
        </div>
    `;

    return card;
}

function togglePostSnippet(postId) {
    const box = document.getElementById(`post-snippet-${postId}`);
    if (!box) return;
    const shortText = box.querySelector('.post-text');
    const fullText = box.querySelector('.post-full-text');
    if (shortText && fullText) {
        shortText.classList.toggle('hidden');
        fullText.classList.toggle('hidden');
    }
}

function setPostFilter(filterType) {
    currentPostFilter = filterType;
    const buttons = document.querySelectorAll('.filter-pills .filter-pill');
    buttons.forEach(b => b.classList.remove('active'));

    const activeBtn = document.getElementById(`filter-post-${filterType}`);
    if (activeBtn) activeBtn.classList.add('active');

    filterPosts();
}

function filterPosts() {
    const searchVal = (document.getElementById('posts-search')?.value || '').toLowerCase().trim();

    let filtered = currentPosts.filter(p => {
        // Filter pills logic
        if (currentPostFilter === 'fresh') {
            const rel = (p.posted_at_relative || '').toLowerCase();
            if (!(rel.includes('h') || rel.includes('1d') || rel.includes('m'))) return false;
        } else if (currentPostFilter === 'dream') {
            if (!p.is_dream_org) return false;
        } else if (currentPostFilter === 'email') {
            if (!p.extracted_emails || p.extracted_emails.length === 0) return false;
        } else if (currentPostFilter === 'engineer') {
            if (p.author_role_category !== 'ENGINEER' && p.author_role_category !== 'PEER') return false;
        } else if (currentPostFilter === 'leader') {
            if (p.author_role_category !== 'LEADER') return false;
        } else if (currentPostFilter === 'recruiter') {
            if (p.author_role_category !== 'RECRUITER') return false;
        }

        // Search input logic
        if (searchVal) {
            const combined = `${p.author_name} ${p.company_name} ${p.author_headline} ${p.post_text}`.toLowerCase();
            if (!combined.includes(searchVal)) return false;
        }

        return true;
    });

    renderHiringPosts(filtered);
}

async function triggerPostDiscovery() {
    showToast('Starting background LinkedIn post discovery...', 'info');
    try {
        const resp = await fetch('/api/posts/discover', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date_filter: 'past-24h', max_scrolls: 4, headless: true })
        });
        if (resp.ok) {
            showToast('Post discovery running in background! It will scan fresh content search updates.', 'success');
            setTimeout(loadHiringPosts, 6000);
        } else {
            showToast('Failed to trigger post discovery', 'error');
        }
    } catch (e) {
        showToast(`Discovery error: ${e.message}`, 'error');
    }
}

async function openPostOutreachModal(postId) {
    const target = currentPosts.find(p => p.post_id === postId);
    if (!target) return;
    currentActivePost = target;

    const modal = document.getElementById('post-outreach-modal');
    const heading = document.getElementById('post-modal-heading');
    const subtitle = document.getElementById('post-modal-subtitle');
    const badge = document.getElementById('post-modal-badge');
    const statusBadge = document.getElementById('post-modal-status-badge');

    if (heading) heading.innerText = `Outreach: ${target.author_name}`;
    if (subtitle) subtitle.innerText = `${target.company_name || 'Tech Enterprise'} • ${target.author_headline || ''}`;
    if (statusBadge) statusBadge.innerText = target.outreach_status || 'NEW';

    if (badge) {
        badge.innerText = target.is_dream_org
            ? '⭐ TIER-1 DREAM ORG INBOUND LEAD'
            : target.author_role_category === 'ENGINEER'
            ? '🛡️ ENGINEERING REFERRAL LEAD'
            : '📢 INBOUND POST LEAD';
    }

    // Set links
    const linkAuthor = document.getElementById('post-link-author');
    const linkInmailAuthor = document.getElementById('post-link-inmail-author');
    const linkOrig = document.getElementById('post-link-original');

    let postModalUrl = target.post_url || '';
    if (postModalUrl && /\/feed\/update\/[0-9a-f]{8,32}\/?$/i.test(postModalUrl)) {
        if (target.author_profile_url) {
            postModalUrl = target.author_profile_url.includes('/company/')
                ? `${target.author_profile_url.replace(/\/+$/, '')}/posts/`
                : `${target.author_profile_url.replace(/\/+$/, '')}/recent-activity/all/`;
        }
    }
    if (linkAuthor) linkAuthor.href = target.author_profile_url || target.post_url || '#';
    if (linkInmailAuthor) linkInmailAuthor.href = target.author_profile_url || target.post_url || '#';
    if (linkOrig) linkOrig.href = postModalUrl || target.post_url || '#';

    // Populate DMs via server or fallback
    try {
        const resp = await fetch(`/api/posts/dm/${postId}`, { method: 'POST' });
        if (resp.ok) {
            const data = await resp.json();
            document.getElementById('post-dm-text').value = data.connection_note || target.custom_dm_draft || '';
            document.getElementById('post-inmail-text').value = data.inmail_pitch || target.custom_inmail_draft || '';

            const tabEmail = document.getElementById('post-tab-email');
            if (data.email_draft) {
                if (tabEmail) tabEmail.classList.remove('hidden');
                document.getElementById('post-email-to').innerText = data.email_draft.to;
                document.getElementById('post-email-subject').innerText = data.email_draft.subject;
                document.getElementById('post-email-text').value = data.email_draft.body;
                document.getElementById('post-email-mailto').href = `mailto:${data.email_draft.to}?subject=${encodeURIComponent(data.email_draft.subject)}&body=${encodeURIComponent(data.email_draft.body)}`;
            } else {
                if (tabEmail) tabEmail.classList.add('hidden');
            }
        }
    } catch (e) {
        document.getElementById('post-dm-text').value = target.custom_dm_draft || '';
        document.getElementById('post-inmail-text').value = target.custom_inmail_draft || '';
    }

    updatePostDmCounter();
    updatePostInmailCounter();
    switchPostModalTab('dm');

    if (modal) modal.classList.remove('hidden');
}

function closePostOutreachModal() {
    const modal = document.getElementById('post-outreach-modal');
    if (modal) modal.classList.add('hidden');
    currentActivePost = null;
}

function handlePostModalOverlayClick(e) {
    if (e.target.id === 'post-outreach-modal') {
        closePostOutreachModal();
    }
}

function switchPostModalTab(tab) {
    const tabDm = document.getElementById('post-tab-dm');
    const tabInmail = document.getElementById('post-tab-inmail');
    const tabEmail = document.getElementById('post-tab-email');
    const paneDm = document.getElementById('post-pane-dm');
    const paneInmail = document.getElementById('post-pane-inmail');
    const paneEmail = document.getElementById('post-pane-email');

    [tabDm, tabInmail, tabEmail].forEach(t => t && t.classList.remove('active'));
    [paneDm, paneInmail, paneEmail].forEach(p => p && p.classList.add('hidden'));

    if (tab === 'dm') {
        if (tabDm) tabDm.classList.add('active');
        if (paneDm) paneDm.classList.remove('hidden');
    } else if (tab === 'inmail') {
        if (tabInmail) tabInmail.classList.add('active');
        if (paneInmail) paneInmail.classList.remove('hidden');
    } else if (tab === 'email') {
        if (tabEmail) tabEmail.classList.add('active');
        if (paneEmail) paneEmail.classList.remove('hidden');
    }
}

function updatePostDmCounter() {
    const textEl = document.getElementById('post-dm-text');
    const counterEl = document.getElementById('post-dm-counter');
    if (!textEl || !counterEl) return;
    const len = textEl.value.length;
    counterEl.innerText = `${len} / 300`;
    if (len > 300) {
        counterEl.classList.add('counter-exceeded');
    } else {
        counterEl.classList.remove('counter-exceeded');
    }
}

function updatePostInmailCounter() {
    const textEl = document.getElementById('post-inmail-text');
    const counterEl = document.getElementById('post-inmail-counter');
    if (!textEl || !counterEl) return;
    const len = textEl.value.length;
    counterEl.innerText = `${len} / 1000`;
    if (len > 1000) {
        counterEl.classList.add('counter-exceeded');
    } else {
        counterEl.classList.remove('counter-exceeded');
    }
}

function copyPostDmNote() {
    const textEl = document.getElementById('post-dm-text');
    if (!textEl) return;
    copyTextToClipboard(textEl.value, 'Connection request note copied to clipboard!');
}

function copyPostInmail() {
    const textEl = document.getElementById('post-inmail-text');
    if (!textEl) return;
    copyTextToClipboard(textEl.value, 'InMail pitch copied to clipboard!');
}

function copyPostEmail() {
    const textEl = document.getElementById('post-email-text');
    if (!textEl) return;
    copyTextToClipboard(textEl.value, 'Email body copied to clipboard!');
}

async function markPostModalContacted() {
    if (!currentActivePost) return;
    await markPostContacted(currentActivePost.post_id);
    closePostOutreachModal();
}

async function markPostContacted(postId) {
    try {
        const resp = await fetch('/api/posts/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ post_id: postId, status: 'CONTACTED' })
        });
        if (resp.ok) {
            showToast('Lead marked as contacted!', 'success');
            const p = currentPosts.find(item => item.post_id === postId);
            if (p) p.outreach_status = 'CONTACTED';
            renderHiringPosts(currentPosts);
            updateQueueBadges();
        }
    } catch (e) {
        showToast(`Failed to update status: ${e.message}`, 'error');
    }
}

async function dismissPost(postId) {
    try {
        const resp = await fetch(`/api/posts/${postId}`, { method: 'DELETE' });
        if (resp.ok) {
            showToast('Post dismissed', 'info');
            currentPosts = currentPosts.filter(item => item.post_id !== postId);
            renderHiringPosts(currentPosts);
            updateQueueBadges();
        }
    } catch (e) {
        showToast(`Failed to dismiss: ${e.message}`, 'error');
    }
}

