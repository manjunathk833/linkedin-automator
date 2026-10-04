let currentJobs = [];
let currentJobIndex = 0;
let approvedJobs = [];
let approvedCount = 0;
let activeTab = 'pending';
let selectedResumeVersion = 'tailored'; // 'tailored' or 'standard'
let currentModalTab = 'tailored';

// --- Tab Switching ---
function switchTab(tab) {
    activeTab = tab;
    const tabPending = document.getElementById('tab-pending');
    const tabApproved = document.getElementById('tab-approved');
    const secPending = document.getElementById('pending-section');
    const secApproved = document.getElementById('approved-section');

    if (tab === 'pending') {
        tabPending.classList.add('active');
        tabApproved.classList.remove('active');
        secPending.classList.remove('hidden');
        secApproved.classList.add('hidden');
        if (currentJobs.length > 0 && currentJobIndex < currentJobs.length) {
            renderJob(currentJobIndex);
        }
    } else {
        tabApproved.classList.add('active');
        tabPending.classList.remove('active');
        secApproved.classList.remove('hidden');
        secPending.classList.add('hidden');
        fetchApprovedJobs();
    }
}

// --- Status Badges & Toasts ---
function updateQueueBadges() {
    const queueCountEl = document.getElementById('queue-count');
    const approvedCountEl = document.getElementById('approved-count');
    const emptyApprovedCountEl = document.getElementById('empty-approved-count');

    if (queueCountEl) queueCountEl.innerText = currentJobs.length;
    if (approvedCountEl) approvedCountEl.innerText = approvedCount;
    if (emptyApprovedCountEl) emptyApprovedCountEl.innerText = approvedCount;
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
    const src = (job.source_platform || job.source || 'ATS').toUpperCase();
    const sourceEl = document.getElementById('job-source-badge');
    if (sourceEl) {
        sourceEl.innerText = `${src} APPLICATION`;
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

    if (version === 'standard') {
        if (tabStandard) tabStandard.classList.add('active');
        if (tabTailored) tabTailored.classList.remove('active');
        if (selectionLabel) selectionLabel.innerText = '📄 Standard Base Resume';
        if (chooseBtn) chooseBtn.innerText = '✓ Select Standard Base Version';
        if (iframe) {
            if (spinner) spinner.classList.remove('hidden');
            iframe.onload = () => { if (spinner) spinner.classList.add('hidden'); };
            iframe.src = '/api/pdf/standard';
        }
    } else {
        if (tabTailored) tabTailored.classList.add('active');
        if (tabStandard) tabStandard.classList.remove('active');
        if (selectionLabel) selectionLabel.innerText = '✨ Tailored Resume';
        if (chooseBtn) chooseBtn.innerText = '✓ Select Tailored Version';
        const job = currentJobs[currentJobIndex];
        if (iframe && job) {
            if (spinner) spinner.classList.remove('hidden');
            iframe.onload = () => { if (spinner) spinner.classList.add('hidden'); };
            iframe.src = `/api/pdf/preview/${job.job_id}?version=tailored`;
        }
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

        const source = (job.source || 'ATS').toLowerCase();
        let pillClass = 'source-pill ';
        if (source.includes('greenhouse')) pillClass += 'greenhouse';
        else if (source.includes('lever')) pillClass += 'lever';
        else if (source.includes('ashby')) pillClass += 'ashby';
        else pillClass += 'linkedin';

        const keywordsHtml = (job.matched_keywords || []).slice(0, 4)
            .map(k => `<span class="keyword-tag">${k}</span>`).join('');

        card.innerHTML = `
            <div>
                <div class="card-top">
                    <div class="company-title">
                        <h3>${job.company}</h3>
                        <p>${job.title}</p>
                    </div>
                    <span class="${pillClass}">${job.source.toUpperCase()}</span>
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
                    <button class="btn-copilot" onclick="autofillApprovedJob('${job.job_id}', this)">
                        🚀 Launch Copilot
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
        const sourceMatch = (job.source || '').toLowerCase().includes(query);
        return companyMatch || titleMatch || kwMatch || sourceMatch;
    });
    renderApprovedGrid(filtered);
}

async function autofillApprovedJob(jobId, btnElement) {
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
