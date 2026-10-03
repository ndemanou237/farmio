document.addEventListener('DOMContentLoaded', () => {
  const list = document.getElementById('message-list');
  if (!list) return;

  let lastId = list.querySelector('[data-message-id]:last-of-type')?.dataset.messageId || '';
  let stopped = false;
  const scrollToBottom = () => {
    list.scrollTop = list.scrollHeight;
  };

  const appendMessage = (message) => {
    if (list.querySelector(`[data-message-id="${CSS.escape(message.id)}"]`)) return;
    const article = document.createElement('article');
    article.dataset.messageId = message.id;
    article.className = `message-bubble max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${message.is_mine ? 'self-end rounded-br-md bg-emerald-700 text-white' : 'self-start rounded-bl-md border border-slate-200 bg-white text-slate-800'}`;
    const content = document.createElement('p');
    content.className = 'whitespace-pre-wrap break-words text-sm leading-6';
    content.textContent = message.content;
    const time = document.createElement('time');
    time.className = `mt-2 block text-right text-[10px] ${message.is_mine ? 'text-emerald-100' : 'text-slate-400'}`;
    time.dateTime = message.created_at;
    time.textContent = new Intl.DateTimeFormat(undefined, {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(message.created_at));
    article.append(content, time);
    list.append(article);
    lastId = message.id;
  };

  const poll = async () => {
    if (stopped || document.hidden) return;
    const url = new URL(list.dataset.pollUrl, window.location.href);
    if (lastId) url.searchParams.set('after_id', lastId);
    try {
      const response = await fetch(url, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        cache: 'no-store',
      });
      if (response.status === 403 || response.status === 404) {
        stopped = true;
        return;
      }
      if (!response.ok) return;
      const payload = await response.json();
      payload.messages.forEach(appendMessage);
      if (payload.messages.length) scrollToBottom();
    } catch (error) {
      // Les erreurs réseau temporaires sont réessayées au prochain intervalle.
    }
  };

  scrollToBottom();
  const interval = window.setInterval(poll, 5000);
  window.addEventListener('pagehide', () => {
    stopped = true;
    window.clearInterval(interval);
  }, { once: true });
  document.addEventListener('visibilitychange', poll);
});
