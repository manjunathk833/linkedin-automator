let currentJobs = [];
let currentJobIndex = 0;

document.addEventListener('DOMContentLoaded', () => {
    fetchJobs();

    document.getElementById('btn-approve').addEventListener('click', approveJob);
    document.getElementById('btn-reject').addEventListener('click', rejectJob);
});

async function fetchJobs() {
    try {
        const response = await fetch('/api/pending-jobs');
        const data = await response.json();
        currentJobs = data.jobs;
        
        document.getElementById('queue-count').innerText = currentJobs.length;
        document.getElementById('loading').classList.add('hidden');
        
        if (currentJobs.length > 0) {
            renderJob(0);
        } else {
            document.getElementById('empty-state').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error fetching jobs:', error);
    }
}

function renderJob(index) {
    const job = currentJobs[index];
    if (!job) return;
    
    document.getElementById('job-view').classList.remove('hidden');
    
    // Left Col
    document.getElementById('job-title').innerText = job.job_details.title;
    document.getElementById('job-company').innerText = job.job_details.company;
    document.getElementById('job-location').innerText = job.job_details.location;
    document.getElementById('job-reqs').innerText = job.job_details.requirements;
    
    // Right Col
    document.getElementById('cand-name').innerText = job.tailored_resume.personal_details.full_name;
    document.getElementById('cand-email').innerText = job.tailored_resume.personal_details.email;
    
    // Achievements
    const expList = document.getElementById('experience-list');
    expList.innerHTML = '';
    job.tailored_resume.experience_history.forEach(exp => {
        const div = document.createElement('div');
        div.className = 'achievement-item';
        div.innerHTML = `<strong>${exp.role} @ ${exp.company}</strong><br>`;
        exp.achievements.forEach(ach => {
            div.innerHTML += `• ${ach}<br>`;
        });
        exp.tech_tags.forEach(tag => {
            div.innerHTML += `<span class="tech-tag">${tag}</span>`;
        });
        expList.appendChild(div);
    });
    
    // Easy Apply Form
    const form = document.getElementById('easy-apply-form');
    form.innerHTML = '';
    if (job.application_type === 'EASY_APPLY') {
        document.getElementById('easy-apply-section').classList.remove('hidden');
        const answers = job.tailored_resume.easy_apply_answers;
        for (const [key, value] of Object.entries(answers)) {
            const group = document.createElement('div');
            group.className = 'form-group';
            
            const label = document.createElement('label');
            label.innerText = key.replace(/_/g, ' ').toUpperCase();
            
            const input = document.createElement('input');
            input.className = 'form-control';
            
            if (typeof value === 'object' && value !== null) {
                input.value = JSON.stringify(value);
            } else if (value === null || value === undefined) {
                input.value = '';
            } else {
                input.value = value;
            }
            
            input.dataset.key = key;
            input.dataset.type = typeof value;
            
            group.appendChild(label);
            group.appendChild(input);
            form.appendChild(group);
        }
    } else {
        document.getElementById('easy-apply-section').classList.add('hidden');
    }
}

function getEditedPayload() {
    const job = currentJobs[currentJobIndex];
    // Gather edits from form
    if (job.application_type === 'EASY_APPLY') {
        const inputs = document.querySelectorAll('#easy-apply-form input');
        inputs.forEach(input => {
            let val = input.value.trim();
            const key = input.dataset.key;
            
            if (val === '') {
                job.tailored_resume.easy_apply_answers[key] = null;
            } else if (val.toLowerCase() === 'true') {
                job.tailored_resume.easy_apply_answers[key] = true;
            } else if (val.toLowerCase() === 'false') {
                job.tailored_resume.easy_apply_answers[key] = false;
            } else if (val.startsWith('{') || val.startsWith('[')) {
                try {
                    job.tailored_resume.easy_apply_answers[key] = JSON.parse(val);
                } catch (e) {
                    job.tailored_resume.easy_apply_answers[key] = val;
                }
            } else if (!isNaN(val) && val !== '') {
                // If it's a numeric string (like salary min/max)
                job.tailored_resume.easy_apply_answers[key] = Number(val);
            } else {
                job.tailored_resume.easy_apply_answers[key] = val;
            }
        });
    }
    return job;
}

async function approveJob() {
    const job = getEditedPayload();
    const originalBtnText = document.getElementById('btn-approve').innerText;
    document.getElementById('btn-approve').innerText = 'Approving...';
    
    try {
        const response = await fetch(`/api/approve/${job.job_id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(job)
        });
        
        if (response.ok) {
            nextJob();
        } else {
            const errData = await response.json();
            alert(`Approval failed: ${errData.detail || response.statusText}`);
            console.error('Approval failed:', errData);
        }
    } catch (error) {
        alert(`Network error during approval: ${error.message}`);
        console.error('Approval failed', error);
    } finally {
        document.getElementById('btn-approve').innerText = originalBtnText;
    }
}

async function rejectJob() {
    const job = currentJobs[currentJobIndex];
    try {
        await fetch(`/api/reject/${job.job_id}`, { method: 'POST' });
        nextJob();
    } catch (error) {
        console.error('Rejection failed', error);
    }
}

function nextJob() {
    currentJobs.splice(currentJobIndex, 1);
    document.getElementById('queue-count').innerText = currentJobs.length;
    
    if (currentJobs.length > 0) {
        renderJob(currentJobIndex);
    } else {
        document.getElementById('job-view').classList.add('hidden');
        document.getElementById('empty-state').classList.remove('hidden');
    }
}
