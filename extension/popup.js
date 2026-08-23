function setStatus(message, className = '') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = className;
}

async function postTrack(payload) {
    const response = await fetch('http://localhost:8000/api/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Server returned ${response.status}`);
    }
}

// Pre-fill the URL field with the active tab's URL on open.
chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => {
    if (tab && tab.url && !tab.url.startsWith('chrome://')) {
        const urlInput = document.getElementById('m-url');
        if (urlInput) urlInput.value = tab.url;
    }
});

document.getElementById('extract-btn').addEventListener('click', async () => {
    const btn = document.getElementById('extract-btn');
    setStatus('Extracting...');
    btn.disabled = true;

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js'],
        });

        const jobData = results[0].result;

        if (!jobData) throw new Error('Failed to extract data');
        if (jobData.error) throw new Error(jobData.error);

        setStatus('Sending to local API...');
        await postTrack({
            company: jobData.company,
            role: jobData.role,
            jd: jobData.jd,
            url: tab.url,
        });

        setStatus('✅ Success! CV + Cover Letter generating.', 'success');
    } catch (error) {
        setStatus(
            error.message.includes('Failed to fetch')
                ? 'Connection Error - Is the local API running?'
                : error.message,
            'error',
        );
    } finally {
        btn.disabled = false;
    }
});

document.getElementById('manual-btn').addEventListener('click', async () => {
    const btn = document.getElementById('manual-btn');
    const company = document.getElementById('m-company').value.trim();
    const role = document.getElementById('m-role').value.trim();
    const jd = document.getElementById('m-jd').value.trim();
    const url = document.getElementById('m-url').value.trim();

    if (!company || !role || !jd) {
        setStatus('Please fill in Company, Role and Job description.', 'error');
        return;
    }

    btn.disabled = true;
    setStatus('Sending to local API...');

    try {
        await postTrack({ company, role, jd, url });
        setStatus('✅ Success! CV + Cover Letter generating.', 'success');
    } catch (error) {
        setStatus(
            error.message.includes('Failed to fetch')
                ? 'Connection Error - Is the local API running?'
                : error.message,
            'error',
        );
    } finally {
        btn.disabled = false;
    }
});
