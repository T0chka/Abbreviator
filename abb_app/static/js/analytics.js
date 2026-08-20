const SESSION_PATH_RE = /\/process\/[^/?#]+\/?/;

window.umamiBeforeSend = function(_type, payload) {
    for (const field of ['url', 'referrer']) {
        if (typeof payload[field] === 'string') {
            payload[field] = payload[field].replace(
                SESSION_PATH_RE, '/process/'
            );
        }
    }
    return payload;
};

document.addEventListener('DOMContentLoaded', () => {
    const results = document.getElementById('resultsAnalytics');
    if (!results || !window.umami) return;

    window.umami.track('results_viewed', {
        source: results.dataset.source,
        abbreviation_count: Number(results.dataset.abbreviationCount),
        has_initial_table: results.dataset.hasInitialTable === 'true',
        initial_table_count: Number(results.dataset.initialTableCount)
    });
});