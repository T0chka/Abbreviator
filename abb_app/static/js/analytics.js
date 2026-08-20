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