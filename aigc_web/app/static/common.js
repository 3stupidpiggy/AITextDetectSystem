const Auth = {
  get token() {
    return localStorage.getItem('aigc_token') || '';
  },
  get username() {
    return localStorage.getItem('aigc_user') || '';
  },
  set(token, username) {
    localStorage.setItem('aigc_token', token);
    localStorage.setItem('aigc_user', username);
  },
  clear() {
    localStorage.removeItem('aigc_token');
    localStorage.removeItem('aigc_user');
  },
};

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// 计算所有人机转折点（0 基）：标签每次变化的位置。空数组表示全篇同一标签。
function computeSwitchPoints(result, sourceText) {
  const words = Array.isArray(result?.words) ? result.words : [];
  const points = [];
  if (words.length < 2) {
    return points;
  }

  const isAi = (w) => Number(w.label_id) === 1 || String(w.label || '').toUpperCase() === 'AIGT';
  const sentences = Array.isArray(result?.sentences) ? result.sentences : [];
  const text = typeof sourceText === 'string' ? sourceText : '';

  let previous = isAi(words[0]);
  for (let i = 1; i < words.length; i += 1) {
    const current = isAi(words[i]);
    if (current === previous) {
      continue;
    }
    points.push({
      wordIndex: i,
      isAI: current,
      sentenceIndex: findSentenceIndexForWord(sentences, text, Number(words[i].start)),
    });
    previous = current;
  }
  return points;
}

function findSentenceIndexForWord(sentences, sourceText, offset) {
  if (!Number.isFinite(offset) || !sourceText) {
    return -1;
  }
  let cursor = 0;
  for (let i = 0; i < sentences.length; i += 1) {
    const sentenceText = String(sentences[i].text || '');
    if (!sentenceText) {
      continue;
    }
    const position = sourceText.indexOf(sentenceText, cursor);
    if (position < 0) {
      continue;
    }
    if (offset >= position && offset < position + sentenceText.length) {
      return i;
    }
    cursor = position + sentenceText.length;
  }
  return -1;
}

function renderSwitchInfo(el, result, points) {
  if (!el) {
    return;
  }
  if (!points || !points.length) {
    const words = Array.isArray(result?.words) ? result.words : [];
    if (!words.length) {
      el.textContent = '切换点：暂无';
      return;
    }
    const allAi = words.every((w) => Number(w.label_id) === 1 || String(w.label || '').toUpperCase() === 'AIGT');
    el.textContent = allAi ? '切换点：全篇判定为 AI' : '切换点：全篇判定为人类';
    return;
  }

  const parts = points.map((point) => {
    const segments = [];
    if (point.sentenceIndex >= 0) {
      segments.push(`第 ${point.sentenceIndex + 1} 句`);
    }
    segments.push(`第 ${point.wordIndex + 1} 个词`);
    return `${segments.join(' · ')}（${point.isAI ? 'AI 起点' : '回到人类'}）`;
  });
  el.innerHTML = `切换点：<strong>${parts.join(' → ')}</strong>`;
}

// 根据 token 的 start/end 在原文上还原高亮，保留标点和换行（中文没有空格也正确）。
// 无法使用 span（例如旧数据没存 start/end）时退回按空格拼接。
function renderWordSpans(container, words, sourceText, options) {
  if (!container) {
    return;
  }
  if (!words || !words.length) {
    container.textContent = '暂无结果';
    return;
  }

  const points = options && Array.isArray(options.switchPoints) ? options.switchPoints : [];
  const markerKinds = new Map();
  points.forEach((point) => {
    const index = Number(point.wordIndex);
    if (Number.isFinite(index) && index >= 0) {
      markerKinds.set(index, point.isAI ? 'to-ai' : 'to-human');
    }
  });
  const markerFor = (index) => {
    const kind = markerKinds.get(index);
    if (!kind) {
      return '';
    }
    const label = kind === 'to-ai' ? 'AI 起点' : '回到人类';
    return `<span class="switch-marker ${kind}" title="${label}"></span>`;
  };

  const text = typeof sourceText === 'string' ? sourceText : '';
  const usable = text.length > 0 && words.every((w) => {
    const start = Number(w.start);
    const end = Number(w.end);
    return Number.isFinite(start) && Number.isFinite(end)
      && start >= 0 && end <= text.length && end > start;
  });

  const spanHtml = (content, word, isAi) => {
    const label = isAi ? 'AIGT' : 'HWT';
    const confidence = word.confidence ?? '-';
    return `<span class="word ${isAi ? 'aigt' : 'hwt'}" title="${label} | 置信度 ${confidence}">${escapeHtml(content)}</span>`;
  };

  if (!usable) {
    container.innerHTML = words
      .map((w, index) => {
        const isAi = Number(w.label_id) === 1 || String(w.label || '').toUpperCase() === 'AIGT';
        return markerFor(index) + spanHtml(String(w.token ?? ''), w, isAi);
      })
      .join(' ');
    return;
  }

  let html = '';
  let cursor = 0;
  for (let index = 0; index < words.length; index += 1) {
    const w = words[index];
    const start = Number(w.start);
    const end = Number(w.end);
    if (start > cursor) {
      html += escapeHtml(text.slice(cursor, start));
    }
    html += markerFor(index);
    const isAi = Number(w.label_id) === 1 || String(w.label || '').toUpperCase() === 'AIGT';
    html += spanHtml(text.slice(start, end), w, isAi);
    cursor = end;
  }
  if (cursor < text.length) {
    html += escapeHtml(text.slice(cursor));
  }
  container.innerHTML = html;
}

async function api(path, method = 'GET', body = null, needAuth = false) {
  const headers = {};
  if (needAuth) {
    if (!Auth.token) {
      throw new Error('请先登录');
    }
    headers.Authorization = `Bearer ${Auth.token}`;
  }

  let requestBody = null;
  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== null && body !== undefined) {
    headers['Content-Type'] = 'application/json';
    requestBody = JSON.stringify(body);
  }

  const resp = await fetch(path, {
    method,
    headers,
    body: requestBody,
  });

  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const error = new Error(data.detail || '请求失败');
    error.detail = data.detail;
    throw error;
  }
  return data;
}

function requireLogin() {
  if (!Auth.token) {
    window.location.href = '/login';
    return false;
  }
  return true;
}

function mountUserInfo(elUser, onLogout) {
  if (elUser) {
    elUser.textContent = `当前用户: ${Auth.username || '未知用户'}`;
  }
  if (typeof onLogout === 'function') {
    onLogout();
  }
}
