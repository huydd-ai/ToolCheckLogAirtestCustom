document.addEventListener('alpine:init', () => {
    Alpine.data('dashboard', () => ({
        // state
        runs: [],
        metrics: null,
        catalog: {},
        tab: 'report', // 'report' or 'catalog'
        loading: false,
        online: true,
        apiError: '',
        etag: '',
        jobs: {}, // { folder_name: {status, job_id} }
        logView: { key: null, text: '', offset: 0, jobId: null }, // one open log panel at a time
        _logFetchInFlight: false,
        batchCancelled: false, // set by cancelAllTests() to abort a Run All loop
        lastUpdated: null,
        gameBenchmarks: null,
        backendBenchmarks: null,
        benchmarkMode: 'normal',
        scoreModalOpen: false,
        selectedScoreData: null,
        metricModalOpen: false,
        selectedMetricData: null,

        metricGuide: [], // 12 benchmark definitions — single source, fetched from /static/metric_guide.json

        // filters
        searchQuery: '',
        filterStatus: 'all',
        filterDevice: '',
        filterSuite: '',
        
        // emulator & catalog search
        emulatorActive: false,
        emulatorLoading: false,
        activeDevices: [],
        catalogSearchQuery: '',
        
        // device uptime tracker
        deviceUptimeStart: null,
        deviceUptimeSeconds: 0,
        uptimeTimer: null,
        
        // scroll state
        showBackToTop: false,

        async init() {
            window.addEventListener('scroll', () => {
                this.showBackToTop = window.scrollY > 300;
            });

            await this.fetchMetricGuide();
            await this.refreshAllData();

            // Adaptive realtime loop: poll fast (2s) while a job runs, slow (10s) when idle.
            // Skips hidden tabs; refetches instantly when the tab regains focus so numbers
            // are never stale on return. Self-scheduling setTimeout so the interval can change.
            const tick = async () => {
                if (!document.hidden) await this.refreshAllData();
                this._pollTimer = setTimeout(tick, this.anyRunning ? 2000 : 10000);
            };
            this._pollTimer = setTimeout(tick, this.anyRunning ? 2000 : 10000);

            document.addEventListener('visibilitychange', () => {
                if (!document.hidden) this.refreshAllData();
            });

            this.$watch('tab', (val) => {
                if (val === 'benchmark') {
                    this.refreshAllData();
                }
            });

            this.$watch('metrics', () => this.renderChart());
        },

        async refreshAllData() {
            await this.fetchData();
            await this.fetchEmulatorStatus();
            await this.fetchBenchmarks();
        },

        scrollToTop() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        },

        get groupedRuns() {
            // apply filters
            let filtered = this.runs.filter(r => {
                if (this.filterStatus !== 'all' && this.filterStatus !== 'FAILED_ONLY') {
                    if (r.status !== this.filterStatus) return false;
                }
                if (this.filterStatus === 'FAILED_ONLY') {
                    // include FAIL and UNKNOWN (which are active tests)
                    if (r.status !== 'FAIL' && r.status !== 'UNKNOWN') return false;
                }
                if (this.filterDevice && r.device !== this.filterDevice) return false;
                if (this.filterSuite && r.suite !== this.filterSuite) return false;
                if (this.searchQuery && !r.stem.toLowerCase().includes(this.searchQuery.toLowerCase())) return false;
                return true;
            });

            // group by date
            let groups = {};
            filtered.forEach(r => {
                const date = r.when.split('T')[0];
                if (!groups[date]) groups[date] = [];
                groups[date].push(r);
            });
            
            // sort by time descending
            for (let date in groups) {
                groups[date].sort((a, b) => new Date(b.when) - new Date(a.when));
            }
            return groups;
        },

        get filteredCatalog() {
            if (!this.catalog) return {};
            if (!this.catalogSearchQuery) return this.catalog;
            
            let query = this.catalogSearchQuery.toLowerCase();
            let filtered = {};
            
            for (let suite in this.catalog) {
                let matchedTests = this.catalog[suite].filter(t => t.toLowerCase().includes(query));
                if (matchedTests.length > 0 || suite.toLowerCase().includes(query)) {
                    filtered[suite] = matchedTests.length > 0 ? matchedTests : this.catalog[suite];
                }
            }
            return filtered;
        },

        get benchmarks() {
            let bMap = {};
            this.runs.forEach(r => {
                if (r.duration !== null && r.duration > 0 && (r.status === 'PASS' || r.status === 'FAIL')) {
                    if (!bMap[r.stem]) bMap[r.stem] = [];
                    bMap[r.stem].push(r.duration);
                }
            });
            let list = [];
            for (let stem in bMap) {
                let durs = bMap[stem].sort((a,b) => a - b);
                let sum = durs.reduce((a,b) => a+b, 0);
                list.push({
                    stem: stem,
                    runs: durs.length,
                    avg: (sum / durs.length).toFixed(2),
                    median: durs[Math.floor(durs.length/2)].toFixed(2),
                    min: durs[0].toFixed(2),
                    max: durs[durs.length-1].toFixed(2),
                    score: Math.max(0, 100 - Math.round(sum / durs.length)) // Simple formula: 100 - avg time
                });
            }
            return list.sort((a,b) => a.stem.localeCompare(b.stem));
        },

        get benchmarkList() {
            if (this.backendBenchmarks && Object.keys(this.backendBenchmarks).length > 0) {
                return Object.values(this.backendBenchmarks).sort((a,b) => a.stem.localeCompare(b.stem));
            }
            return this.benchmarks;
        },

        get overallScore() {
            let list = this.benchmarkList;
            if (!list || list.length === 0) return 0;
            let sum = list.reduce((acc, b) => acc + (b.score || 0), 0);
            return (sum / list.length).toFixed(1);
        },

        get overallAvgRuntime() {
            let list = this.benchmarkList;
            if (!list || list.length === 0) return 0;
            let sum = list.reduce((acc, b) => acc + (parseFloat(b.avg) || 0), 0);
            return (sum / list.length).toFixed(2);
        },

        openScoreModal(b) {
            if (!b) return;
            const passRate = b.pass_rate !== undefined ? b.pass_rate : 100.0;
            const passScore = +(passRate * 0.70).toFixed(1);
            const avg = parseFloat(b.avg) || 1.0;
            const stddev = parseFloat(b.stddev) || 0.0;
            const varRatio = avg > 0 ? Math.min(1.0, stddev / avg) : 0;
            const stabilityScore = +((1.0 - varRatio) * 30.0).toFixed(1);

            this.selectedScoreData = {
                stem: b.stem,
                suite: b.suite || 'unknown',
                score: b.score !== undefined ? b.score : 100,
                passRate: passRate,
                passScore: passScore,
                stabilityScore: stabilityScore,
                runs: b.runs || 1,
                passCount: b.pass_count || (passRate >= 100 ? b.runs : 0),
                failCount: b.fail_count || 0,
                avg: b.avg,
                median: b.median,
                p90: b.p90 || b.max,
                min: b.min,
                max: b.max,
                stddev: b.stddev !== undefined ? b.stddev : '0.00',
                varRatioPct: (varRatio * 100).toFixed(1)
            };
            this.scoreModalOpen = true;
        },

        closeScoreModal() {
            this.scoreModalOpen = false;
            this.selectedScoreData = null;
        },

        async fetchMetricGuide() {
            try {
                const res = await fetch('/static/metric_guide.json');
                if (res.ok) this.metricGuide = await res.json();
            } catch (e) { /* modals/tables just render empty until it loads */ }
        },

        openMetricModal(key) {
            const m = this.metricGuide.find(g => g.key === key);
            if (!m) return;
            this.selectedMetricData = m;
            this.metricModalOpen = true;
        },

        closeMetricModal() {
            this.metricModalOpen = false;
            this.selectedMetricData = null;
        },

        async fetchData() {
            try {
                this.loading = true;
                const headers = this.etag ? { 'If-None-Match': this.etag } : {};
                const res = await fetch('/api/runs', { headers });
                this.online = true;
                if (res.status === 200) {
                    this.runs = await res.json();
                    this.etag = res.headers.get('ETag');
                    await this.fetchMetrics();
                    await this.fetchCatalog();
                    this.apiError = '';
                    this.lastUpdated = new Date();
                } else if (res.status !== 304) {
                    const body = await res.json().catch(() => ({}));
                    this.apiError = `API error ${res.status}: ${body.error || 'unexpected response'}`;
                }
                // Always refresh benchmarks so live ADB device telemetry updates on every poll
                await this.fetchBenchmarks();
            } catch (err) {
                this.online = false;
            } finally {
                this.loading = false;
            }
        },
        
        async fetchMetrics() {
            const res = await fetch('/api/metrics');
            if (res.ok) this.metrics = await res.json();
        },
        
        async fetchCatalog() {
            const res = await fetch('/api/catalog');
            if (res.ok) this.catalog = await res.json();
        },

        async setBenchmarkMode(mode) {
            this.benchmarkMode = mode;
            await this.fetchBenchmarks();
        },

        get formattedUptime() {
            const totalSec = this.deviceUptimeSeconds || 0;
            const hrs = Math.floor(totalSec / 3600);
            const mins = Math.floor((totalSec % 3600) / 60);
            const secs = totalSec % 60;
            const pad = (n) => String(n).padStart(2, '0');
            if (hrs > 0) {
                return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`;
            }
            return `${pad(mins)}:${pad(secs)}`;
        },

        updateUptimeTracker() {
            const hasLiveDevs = this.gameBenchmarks?.live_devices && this.gameBenchmarks.live_devices.length > 0;
            const hasActiveDevs = this.activeDevices && this.activeDevices.length > 0;
            const isAnyActive = Boolean(this.emulatorActive || hasLiveDevs || hasActiveDevs);
            
            if (isAnyActive) {
                if (!this.deviceUptimeStart) {
                    this.deviceUptimeStart = Date.now();
                }
                if (!this.uptimeTimer) {
                    this.uptimeTimer = setInterval(() => {
                        if (this.deviceUptimeStart) {
                            this.deviceUptimeSeconds = Math.floor((Date.now() - this.deviceUptimeStart) / 1000);
                        }
                    }, 1000);
                }
            } else {
                // Reset running time when device turns off
                this.deviceUptimeStart = null;
                this.deviceUptimeSeconds = 0;
                if (this.uptimeTimer) {
                    clearInterval(this.uptimeTimer);
                    this.uptimeTimer = null;
                }
            }
        },

        async fetchBenchmarks() {
            try {
                const res = await fetch(`/api/benchmarks?mode=${this.benchmarkMode}`);
                if (res.ok) {
                    const data = await res.json();
                    this.gameBenchmarks = data.game_benchmarks;
                    this.backendBenchmarks = data.benchmarks;
                }
            } catch (e) {}
            this.updateUptimeTracker();
        },

        async fetchEmulatorStatus() {
            try {
                const res = await fetch('/emulator/status');
                if (res.ok) {
                    const data = await res.json();
                    this.emulatorActive = data.active;
                    this.activeDevices = data.devices || [];
                }
            } catch (e) {
                this.emulatorActive = false;
                this.activeDevices = [];
            }
            this.updateUptimeTracker();
        },

        renderChart() {
            if (!this.metrics || !this.metrics.trend) return;
            const ctx = document.getElementById('trendChart');
            if (!ctx) return;

            // Pad a synthetic previous day when there is a single point so the
            // line chart can draw a line (presentation-only; API returns real dates).
            let trend = this.metrics.trend;
            if (trend.length === 1) {
                const d = new Date(trend[0].date + 'T00:00:00Z');
                d.setUTCDate(d.getUTCDate() - 1);
                const prev = d.toISOString().slice(0, 10);
                trend = [{ date: prev, total: 0, pass_rate: trend[0].pass_rate }, ...trend];
            }
            const labels = trend.map(t => t.date);
            const passRates = trend.map(t => t.pass_rate);
            const totals = trend.map(t => t.total);
            
            if (this.chartInstance) {
                this.chartInstance.data.labels = labels;
                this.chartInstance.data.datasets[0].data = passRates;
                this.chartInstance.data.datasets[1].data = totals;
                this.chartInstance.update('none'); // Update without animation to prevent flicker
                return;
            }
            
            this.chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Pass Rate (%)',
                            data: passRates,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.04)',
                            yAxisID: 'y',
                            fill: true,
                            tension: 0.3,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            borderWidth: 2
                        },
                        {
                            label: 'Total Runs',
                            data: totals,
                            type: 'bar',
                            backgroundColor: 'rgba(99, 102, 241, 0.4)',
                            borderColor: 'rgba(99, 102, 241, 0.6)',
                            borderWidth: 1,
                            yAxisID: 'y1',
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: { 
                            type: 'linear', 
                            position: 'left', 
                            min: 0, 
                            max: 100,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                        },
                        y1: { 
                            type: 'linear', 
                            position: 'right', 
                            min: 0, 
                            grid: { drawOnChartArea: false },
                            ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                        },
                        x: {
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: '#94a3b8', font: { family: 'Inter' } }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#f8fafc', font: { family: 'Inter', weight: '500' } } }
                    }
                }
            });
        },

        async startEmulator() {
            try {
                const res = await fetch('/emulator/start', { method: 'POST' });
                return res.ok;
            } catch (e) {
                return false;
            }
        },

        async stopEmulator() {
            try {
                await fetch('/emulator/stop', { method: 'POST' });
            } catch (e) { /* best-effort close */ }
        },

        async manuallyStartEmulator() {
            this.emulatorLoading = true;
            await this.startEmulator();
            this.emulatorLoading = false;
            await this.fetchEmulatorStatus();
        },

        async manuallyStopEmulator() {
            this.emulatorLoading = true;
            await this.stopEmulator();
            this.emulatorLoading = false;
            await this.fetchEmulatorStatus();
        },

        async rerunTest(folder) {
            this.jobs[folder] = { status: 'starting emulator...' };
            if (!await this.startEmulator()) {
                this.jobs[folder] = { status: 'emulator failed to start' };
                return;
            }
            this.jobs[folder] = { status: 'starting...' };
            try {
                const res = await fetch('/rerun/' + encodeURIComponent(folder), { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    this.jobs[folder] = { status: 'running', job_id: data.job_id };
                    this.pollJob(data.job_id, folder); // standalone -> stops emulator on finish
                } else {
                    this.jobs[folder] = { status: 'failed to start' };
                }
            } catch (err) {
                this.jobs[folder] = { status: 'error' };
            }
        },

        async runCatalogTest(suite, stem, standalone = true) {
            const key = stem;
            if (standalone) {
                this.jobs[key] = { status: 'starting emulator...' };
                if (!await this.startEmulator()) {
                    this.jobs[key] = { status: 'emulator failed to start' };
                    return false;
                }
            }
            this.jobs[key] = { status: 'starting...' };
            try {
                const res = await fetch('/run', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({air_path: `Test/${suite}/${stem}.air`})
                });
                const data = await res.json();
                if (res.ok) {
                    this.jobs[key] = { status: 'running', job_id: data.job_id };
                    return this.pollJob(data.job_id, key, standalone); // stop only if standalone
                } else {
                    this.jobs[key] = { status: 'failed to start' };
                    return false;
                }
            } catch(err) {
                this.jobs[key] = { status: 'error' };
                return false;
            }
        },

        async runSuite(suite) {
            const tests = this.catalog[suite];
            if (!tests) return;
            if (!confirm(`Run all ${tests.length} tests in ${suite} sequentially?\n\nKeep this tab open until all tests finish.`)) return;

            if (!await this.startEmulator()) {
                alert('Emulator failed to start — batch aborted.');
                return;
            }
            this.batchCancelled = false;
            try {
                for (const t of tests) {
                    if (this.batchCancelled) break;
                    if (this.jobs[t]?.status === 'running') continue;

                    await this.runCatalogTest(suite, t, false); // batch: no per-test open/close

                    // wait 3 seconds between tests to let device settle
                    await new Promise(r => setTimeout(r, 3000));
                }
            } finally {
                await this.stopEmulator(); // close once after the whole batch
            }
        },

        toggleLogs(key) {
            if (this.logView.key === key) {
                this.logView = { key: null, text: '', offset: 0, jobId: null };
            } else {
                this.logView = { key: key, text: '', offset: 0, jobId: null };
                this.fetchLogs();
            }
        },

        async fetchLogs() {
            if (this._logFetchInFlight) return;
            this._logFetchInFlight = true;
            try {
                const key = this.logView.key;
                if (!key) return;
                const jobId = this.jobs[key]?.job_id;
                if (!jobId) return;
                if (this.logView.jobId !== jobId) {
                    this.logView.text = '';
                    this.logView.offset = 0;
                    this.logView.jobId = jobId;
                }
                try {
                    const res = await fetch(`/rerun-logs/${encodeURIComponent(jobId)}?offset=${this.logView.offset}`);
                    if (!res.ok) return;
                    const data = await res.json();
                    if (this.logView.key !== key) return; // panel switched while fetching
                    if (data.text) this.logView.text += data.text;
                    this.logView.offset = data.offset;
                } catch (e) { /* next tick retries */ }
            } finally {
                this._logFetchInFlight = false;
            }
        },

        pollJob(jobId, key, standalone = true) {
            return new Promise(resolve => {
                const interval = setInterval(async () => {
                    if (this.logView.key === key) this.fetchLogs();
                    try {
                        const res = await fetch('/rerun-status/' + encodeURIComponent(jobId));
                        const data = await res.json();
                        if (data.status !== 'running') {
                            clearInterval(interval);
                            this.jobs[key] = { status: data.status === 'done' ? 'completed' : 'failed', job_id: jobId };
                            if (this.logView.key === key) await this.fetchLogs();
                            if (standalone) await this.stopEmulator(); // close on any terminal state
                            this.etag = ''; // force reload on next fetch
                            this.fetchData();
                            resolve(data.status);
                        }
                    } catch(e) {
                        clearInterval(interval);
                        this.jobs[key] = { status: 'poll error', job_id: jobId };
                        resolve('error');
                    }
                }, 2000);
            });
        },

        async terminateTest(jobId, key) {
            try {
                await fetch('/rerun-terminate/' + encodeURIComponent(jobId), { method: 'POST' });
            } catch (err) {}
        },

        get anyRunning() {
            return Object.values(this.jobs).some(j => j?.status === 'running');
        },

        async cancelAllTests() {
            if (!confirm('Cancel ALL running tests?')) return;
            this.batchCancelled = true; // abort any in-progress Run All loop
            try {
                await fetch('/terminate-all', { method: 'POST' });
            } catch (err) {}
            // pollJob picks up the terminated status and updates each job row
        },

        async deleteRun(folder) {
            if (!confirm('Delete ' + folder + '?')) return;
            try {
                const res = await fetch('/delete/' + encodeURIComponent(folder), { method: 'POST' });
                if (res.ok) {
                    this.etag = '';
                    this.fetchData();
                } else {
                    const body = await res.json().catch(() => ({}));
                    this.apiError = `Delete failed (${res.status}): ${body.error || 'unexpected response'}`;
                }
            } catch (err) {
                this.apiError = 'Delete failed: ' + err;
            }
        },

        async deleteDate(dateStr) {
            if (!confirm('Delete all runs on ' + dateStr + '?')) return;
            try {
                const res = await fetch('/delete-date/' + encodeURIComponent(dateStr), { method: 'POST' });
                if (res.ok) {
                    this.etag = '';
                    this.fetchData();
                } else {
                    const body = await res.json().catch(() => ({}));
                    this.apiError = `Delete failed (${res.status}): ${body.error || 'unexpected response'}`;
                }
            } catch (err) {
                this.apiError = 'Delete failed: ' + err;
            }
        },

        copyLogs() {
            if (!this.logView.text) return;
            navigator.clipboard.writeText(this.logView.text)
                .then(() => alert('Log content copied to clipboard!'))
                .catch(() => alert('Failed to copy log.'));
        }
    }));
});
