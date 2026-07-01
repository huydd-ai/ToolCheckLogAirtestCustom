document.addEventListener('alpine:init', () => {
    Alpine.data('dashboard', () => ({
        // state
        runs: [],
        metrics: null,
        catalog: {},
        tab: 'report', // 'report' or 'catalog'
        loading: false,
        online: true,
        etag: '',
        jobs: {}, // { folder_name: {status, job_id} }
        
        // filters
        searchQuery: '',
        filterStatus: 'all',
        filterDevice: '',
        filterSuite: '',
        
        chartInstance: null,

        async init() {
            await this.fetchData();
            setInterval(() => this.fetchData(), 3000);
            
            this.$watch('metrics', () => this.renderChart());
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
                }
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

        renderChart() {
            if (!this.metrics || !this.metrics.trend) return;
            const ctx = document.getElementById('trendChart');
            if (!ctx) return;
            
            const labels = this.metrics.trend.map(t => t.date);
            const passRates = this.metrics.trend.map(t => t.pass_rate);
            const totals = this.metrics.trend.map(t => t.total);
            
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
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            yAxisID: 'y',
                            fill: true,
                            tension: 0.3,
                            pointRadius: 5,
                            pointHoverRadius: 7
                        },
                        {
                            label: 'Total Runs',
                            data: totals,
                            type: 'bar',
                            backgroundColor: 'rgba(59, 130, 246, 0.5)',
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: { type: 'linear', position: 'left', min: 0, max: 100 },
                        y1: { type: 'linear', position: 'right', min: 0, grid: { drawOnChartArea: false } }
                    },
                    plugins: {
                        legend: { labels: { color: '#e2e8f0' } }
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
            try {
                for (const t of tests) {
                    if (this.jobs[t]?.status === 'running') continue;

                    await this.runCatalogTest(suite, t, false); // batch: no per-test open/close

                    // wait 3 seconds between tests to let device settle
                    await new Promise(r => setTimeout(r, 3000));
                }
            } finally {
                await this.stopEmulator(); // close once after the whole batch
            }
        },

        pollJob(jobId, key, standalone = true) {
            return new Promise(resolve => {
                const interval = setInterval(async () => {
                    try {
                        const res = await fetch('/rerun-status/' + encodeURIComponent(jobId));
                        const data = await res.json();
                        if (data.status !== 'running') {
                            clearInterval(interval);
                            this.jobs[key] = { status: data.status === 'done' ? 'completed' : 'failed' };
                            if (standalone) await this.stopEmulator(); // close on any terminal state
                            this.etag = ''; // force reload on next fetch
                            this.fetchData();
                            resolve(data.status);
                        }
                    } catch(e) {
                        clearInterval(interval);
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

        async deleteRun(folder) {
            if (!confirm('Delete ' + folder + '?')) return;
            try {
                const res = await fetch('/delete/' + encodeURIComponent(folder), { method: 'POST' });
                if (res.ok) {
                    this.etag = '';
                    this.fetchData();
                }
            } catch (err) {}
        },
        
        async deleteDate(dateStr) {
            if (!confirm('Delete all runs on ' + dateStr + '?')) return;
            try {
                const res = await fetch('/delete-date/' + encodeURIComponent(dateStr), { method: 'POST' });
                if (res.ok) {
                    this.etag = '';
                    this.fetchData();
                }
            } catch (err) {}
        }
    }));
});
