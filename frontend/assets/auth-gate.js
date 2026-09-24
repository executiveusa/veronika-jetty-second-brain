const config = window.JETTY_CONFIG || {};
const privatePage = location.pathname.startsWith('/app') || location.pathname.startsWith('/wellness');
const originalFetch = window.fetch.bind(window);

function apiRequest(input) {
  const value = typeof input === 'string' ? input : input?.url || '';
  try { return new URL(value, location.href).pathname.startsWith('/api/'); }
  catch { return false; }
}

function installAuthenticatedFetch(token) {
  window.JETTY_ACCESS_TOKEN = token;
  window.fetch = (input, init = {}) => {
    if (!apiRequest(input)) return originalFetch(input, init);
    const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
    headers.set('Authorization', `Bearer ${window.JETTY_ACCESS_TOKEN}`);
    return originalFetch(input, { ...init, headers });
  };
}

function showGate(message, supabase) {
  document.body.innerHTML = `<main style="max-width:360px;margin:14vh auto;padding:24px;font-family:Sora,sans-serif">
    <h1>JETTY™</h1><p>${message}</p>
    ${supabase ? '<label>Email<input id="auth-email" type="email" autocomplete="email" style="display:block;width:100%;padding:12px;margin:8px 0 14px"></label><label>Password<input id="auth-password" type="password" autocomplete="current-password" style="display:block;width:100%;padding:12px;margin:8px 0 14px"></label><button id="auth-sign-in" style="padding:12px 18px">Sign in</button><p id="auth-error" role="alert"></p>' : ''}
  </main>`;
  if (!supabase) return;
  document.getElementById('auth-sign-in').onclick = async () => {
    const { error } = await supabase.auth.signInWithPassword({email:document.getElementById('auth-email').value,password:document.getElementById('auth-password').value});
    if (error) document.getElementById('auth-error').textContent = error.message;
    else location.reload();
  };
}

if (privatePage) {
  document.documentElement.style.visibility = 'hidden';
  const ready = (async () => {
    if (!config.supabaseUrl || !config.supabaseAnonKey) {
      document.documentElement.style.visibility = '';
      showGate('Sign-in is not configured for this deployment.');
      return;
    }
    const { createClient } = await import('https://esm.sh/@supabase/supabase-js@2');
    const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      document.documentElement.style.visibility = '';
      showGate('Sign in to open your Jetty workspace.', supabase);
      return;
    }
    installAuthenticatedFetch(session.access_token);
    document.documentElement.style.visibility = '';
  })();
  window.JETTY_AUTH_READY = ready;
}
