document.getElementById('extract-btn').addEventListener('click', async () => {
    const statusEl = document.getElementById('status');
    const btn = document.getElementById('extract-btn');
    
    statusEl.textContent = 'Extracting...';
    statusEl.className = '';
    btn.disabled = true;

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        const results = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content.js']
        });
        
        const jobData = results[0].result;
        
        if (!jobData) {
            throw new Error("Failed to extract data");
        }
        
        if (jobData.error) {
            throw new Error(jobData.error);
        }
        
        statusEl.textContent = 'Sending to local API...';
        
        // As per spec: "system SHALL send a POST request to http://localhost:8000/api/track"
        const response = await fetch('http://localhost:8000/api/track', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                company: jobData.company,
                role: jobData.role,
                jd: jobData.jd
            })
        });
        
        if (!response.ok) {
            throw new Error("Server returned " + response.status);
        }
        
        statusEl.textContent = '✅ Success! CV is generating.';
        statusEl.className = 'success';
        
    } catch (error) {
        statusEl.textContent = error.message.includes('Failed to fetch') 
            ? "Connection Error - Is the local API running?" 
            : error.message;
        statusEl.className = 'error';
    } finally {
        btn.disabled = false;
    }
});
