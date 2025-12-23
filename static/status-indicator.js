/**
 * Status Indicator - Client-side state management for system health display.
 *
 * Polls the /status/ endpoint and updates UI with current system status.
 */

class StatusIndicator {
    static STATUS_COLORS = {
        operational: '#28a745',  // Green
        degraded: '#ffc107',     // Yellow
        down: '#dc3545',         // Red
        loading: '#6c757d',      // Gray
        unknown: '#6c757d',      // Gray
    };

    static STATUS_LABELS = {
        operational: 'All Systems Operational',
        degraded: 'Partial System Outage',
        down: 'Major System Outage',
        loading: 'Checking Status...',
        unknown: 'Status Unknown',
    };

    static POLL_INTERVAL_MS = 60000;  // 60 seconds

    constructor() {
        this._status = 'loading';
        this._statusPageUrl = null;
        this._pollInterval = null;
        this._element = null;
        this._isInitialLoad = true;
    }

    get status() {
        return this._status;
    }

    get statusColor() {
        return StatusIndicator.STATUS_COLORS[this._status] || StatusIndicator.STATUS_COLORS.unknown;
    }

    get statusLabel() {
        return StatusIndicator.STATUS_LABELS[this._status] || StatusIndicator.STATUS_LABELS.unknown;
    }

    get isLoading() {
        return this._status === 'loading';
    }

    get statusPageUrl() {
        return this._statusPageUrl;
    }

    /**
     * Initialize the status indicator and start polling.
     * @param {string} elementId - ID of the DOM element to update
     */
    async initialize(elementId) {
        this._element = document.getElementById(elementId);
        if (!this._element) {
            console.warn(`StatusIndicator: Element with id "${elementId}" not found`);
            return;
        }

        // Initial fetch
        await this._fetchStatus();
        this._isInitialLoad = false;

        // Start polling
        this._pollInterval = setInterval(() => {
            this._fetchStatus();
        }, StatusIndicator.POLL_INTERVAL_MS);

        // Cleanup on page unload
        window.addEventListener('beforeunload', () => this.destroy());
    }

    /**
     * Stop polling and cleanup resources.
     */
    destroy() {
        if (this._pollInterval) {
            clearInterval(this._pollInterval);
            this._pollInterval = null;
        }
    }

    /**
     * Fetch status from the backend proxy endpoint.
     */
    async _fetchStatus() {
        // Only show loading animation on initial load
        if (this._isInitialLoad) {
            this._updateUI('loading');
        }

        try {
            const response = await fetch('/status/', {
                method: 'GET',
                credentials: 'include',
            });

            if (!response.ok) {
                console.warn(`StatusIndicator: Failed to fetch status (${response.status})`);
                this._status = 'unknown';
                this._updateUI(this._status);
                return;
            }

            const data = await response.json();
            this._status = data.status || 'unknown';
            this._statusPageUrl = data.status_page_url || null;
            this._updateUI(this._status);

        } catch (error) {
            console.error('StatusIndicator: Error fetching status:', error);
            this._status = 'unknown';
            this._updateUI(this._status);
        }
    }

    /**
     * Update the DOM element with current status.
     * @param {string} status - Current status value
     */
    _updateUI(status) {
        if (!this._element) return;

        const color = StatusIndicator.STATUS_COLORS[status] || StatusIndicator.STATUS_COLORS.unknown;
        const label = StatusIndicator.STATUS_LABELS[status] || StatusIndicator.STATUS_LABELS.unknown;
        const isLoading = status === 'loading';

        // Update indicator dot
        const dot = this._element.querySelector('.status-dot');
        if (dot) {
            dot.style.backgroundColor = color;
            dot.classList.toggle('status-pulse', isLoading);
        }

        // Update icon color and animation
        const icon = this._element.querySelector('.status-icon');
        if (icon) {
            icon.style.stroke = color;
            icon.classList.toggle('status-pulse', isLoading);
        }

        // Update tooltip/title
        this._element.title = label;

        // Update link href if available
        if (this._statusPageUrl) {
            this._element.href = this._statusPageUrl;
            this._element.style.cursor = 'pointer';
        } else {
            this._element.removeAttribute('href');
            this._element.style.cursor = 'default';
        }
    }
}

// Create singleton instance
const statusIndicator = new StatusIndicator();

// Export for both browser and module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StatusIndicator, statusIndicator };
}
if (typeof window !== 'undefined') {
    window.StatusIndicator = StatusIndicator;
    window.statusIndicator = statusIndicator;
}
