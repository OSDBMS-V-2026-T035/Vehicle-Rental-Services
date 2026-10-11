(() => {
  const app = window.RIDEHUB_PORTAL || {};
  const role = app.role || 'USER';
  const nav = document.querySelector('#portal-nav');
  const content = document.querySelector('#portal-content');
  const crumb = document.querySelector('#crumb-label');
  const toast = document.querySelector('#portal-toast');
  const icon = {overview:'◉', rides:'⌁', bookings:'▣', payments:'₹', transactions:'⇄', profile:'◌', support:'?', vehicles:'▤', availability:'◷', fares:'₹', reservations:'▣', earnings:'↗', shop:'⌖', verification:'✓', users:'◉', shopkeepers:'▥', moderation:'◈', orders:'▣', finance:'₹', cms:'✦', reports:'◫', audit:'◌', settings:'⚙'};
  const specs = {
    USER: {
      heading: 'Welcome back,', subheading: 'Your rider dashboard is ready for the next trip.',
      groups: [
        ['WORKSPACE', [['overview','Overview'],['rides','Find a ride'],['bookings','My bookings'],['payments','Payments & refunds']]],
        ['ACCOUNT', [['transactions','Transactions'],['profile','Profile & security'],['support','Help & support']]]
      ],
      stats: [['⌁','Ride discovery','Search-ready'],['▣','Bookings','Under development'],['₹','Payments','Secure workspace'],['◌','Profile','Protected account']],
      quick: [['rides','Find a ride','Search verified local vehicles and shops'],['bookings','Booking centre','Upcoming, active, completed and cancelled trips'],['payments','Payments & refunds','Invoices, refunds, receipts and payment methods'],['profile','Profile & security','Personal details, login security and preferences']],
      flow: [['Booking timeline','Trip requests, confirmations, pickup and return'],['Account centre','Identity, preferences and notification controls'],['Support hub','Trip assistance, disputes and safety support']]
    },
    SHOPKEEPER: {
      heading: 'Business control,', subheading: 'Manage your rental operation from one protected workspace.',
      groups: [
        ['OPERATIONS', [['overview','Overview'],['vehicles','Vehicle management'],['availability','Availability calendar'],['fares','Fare & pricing'],['reservations','Reservation centre']]],
        ['BUSINESS', [['earnings','Payments & earnings'],['shop','Shop profile'],['verification','Verification status'],['profile','Account & security'],['support','Help & support']]]
      ],
      stats: [['▤','Fleet management','Under development'],['◷','Availability','Calendar planned'],['₹','Revenue & payouts','Secure workspace'],['✓','Shop verification','Review centre']],
      quick: [['vehicles','Vehicle management','Add, edit, archive, photos, documents and listing review'],['availability','Availability calendar','Availability blocks, maintenance windows and blackout dates'],['fares','Fare & pricing','Daily rates, deposits, seasonal pricing and promotions'],['reservations','Reservation centre','Requests, handover checklist, extensions and cancellations'],['earnings','Payments & earnings','Payout history, invoices, commissions and settlement status'],['shop','Shop profile','Address, operating hours, location and public shop details']],
      flow: [['Fleet lifecycle','Draft → review → approved → unavailable or archived'],['Reservation safety','Pickup verification, condition notes and return handover'],['Business controls','Payout preferences, tax records and team permissions']]
    },
    ADMIN: {
      heading: 'Platform command,', subheading: 'A protected control centre for marketplace operations and governance.',
      groups: [
        ['OPERATIONS', [['overview','Overview'],['users','User management'],['shopkeepers','Shopkeeper management'],['vehicles','Vehicle & ride moderation'],['orders','Orders & bookings'],['payments','Payments & disputes']]],
        ['GOVERNANCE', [['finance','Accounts & finance'],['cms','Website CMS'],['reports','Reports & analytics'],['audit','Audit & security log'],['settings','Platform settings'],['profile','Admin profile']]]
      ],
      stats: [['◉','User management','Access controls'],['▥','Shopkeeper review','Verification queue'],['◈','Fleet moderation','Listing compliance'],['₹','Finance centre','Reconciliation planned']],
      quick: [['users','User management','Accounts, access, verification, support actions and risk flags'],['shopkeepers','Shopkeeper management','Onboarding, document review, approval, suspension and lifecycle'],['vehicles','Vehicle & ride moderation','Listing quality, documents, availability and policy compliance'],['orders','Orders & bookings','Booking oversight, cancellations, disputes and service recovery'],['payments','Payments & disputes','Payment status, refunds, chargebacks and dispute resolution'],['finance','Accounts & finance','Payouts, platform revenue, commissions, tax and reconciliation'],['cms','Website CMS','Homepage content, categories, policy pages, banners and announcements'],['reports','Reports & analytics','Marketplace health, operations, finance and security reports'],['audit','Audit & security log','Admin actions, critical events and retention controls'],['settings','Platform settings','Roles, permissions, service configuration and feature controls']],
      flow: [['Moderation workflow','Review → request changes → approve / reject / suspend'],['Finance workflow','Payments → refunds → payouts → reconciliation'],['Risk & accountability','Least-privilege roles, audit records and secure escalation paths']]
    }
  };
  const current = specs[role] || specs.USER;
  const titleFor = key => current.groups.flatMap(([, items]) => items).find(([id]) => id === key)?.[1] || 'Overview';
  let currentPage = 'overview';

  const showToast = text => { toast.textContent = text; toast.classList.add('show'); clearTimeout(window.portalToastTimer); window.portalToastTimer = setTimeout(() => toast.classList.remove('show'), 3100); };
  const moduleList = items => `<div class="module-list">${items.map(([key,title,desc]) => `<button class="module-row" data-page="${key}"><span class="mini-icon">${icon[key] || '◈'}</span><span><strong>${title}</strong><small>${desc}</small></span><span class="status-tag">PLANNED</span></button>`).join('')}</div>`;
  const launchCards = items => `<div class="launch-grid">${items.map(([key,title,desc]) => `<button class="launch-card" data-page="${key}"><span class="mini-icon">${icon[key] || '◈'}</span><strong>${title}</strong><small>${desc}</small></button>`).join('')}</div>`;
  const renderOverview = () => {
    const shortName = (app.name || 'there').split(' ')[0];
    content.innerHTML = `<div class="hero-line"><div><p class="eyebrow">${app.label || 'RIDEHUB'} PORTAL</p><h1>${current.heading} <span>${escape(shortName)}.</span></h1><p>${current.subheading}</p></div><span class="development-pill">FRONTEND PREVIEW · UNDER DEVELOPMENT</span></div><div class="notice-bar">✦ This dashboard is a visual frontend preview. Actions, data and integrations will be connected in the next phase.</div><div class="dashboard-grid">${current.stats.map(([ico,label,detail]) => `<article class="card stat-card"><span class="stat-icon">${ico}</span><h3>—</h3><p>${label}</p><small>${detail}</small></article>`).join('')}<article class="card wide-card"><div class="card-head"><div><h2>Workspace modules</h2><p>Explore each planned function and workflow.</p></div><button class="ghost-button" data-coming-soon="All dashboard functionality is under development.">View roadmap</button></div>${moduleList(current.quick.slice(0, role === 'ADMIN' ? 6 : 4))}</article><article class="card side-card"><div class="card-head"><div><h2>Build status</h2><p>Feature connections are planned.</p></div></div><div class="empty-state"><div><div class="empty-icon">◌</div><h2>No live data yet</h2><p>Live records, filters and actions will be available after the backend integration phase.</p></div></div></article><article class="card full-card"><div class="card-head"><div><h2>Coming to this portal</h2><p>Designed around the marketplace process and edge cases.</p></div></div>${launchCards(current.quick)}</article></div>`;
  };
  const featureCopy = key => current.quick.find(([id]) => id === key)?.[2] || 'This protected workspace module is planned for the next delivery phase.';
  const renderFeature = key => {
    const title = titleFor(key); const detail = featureCopy(key);
    const safeguards = role === 'ADMIN' ? ['Role-based access and approval rules','Audit trail for sensitive changes','Clear review, rejection and recovery states'] : role === 'SHOPKEEPER' ? ['Draft, pending, approved and rejected states','Availability conflicts and maintenance blocks','Secure records, payout and support boundaries'] : ['Booking states and cancellation boundaries','Payment, refund and receipt lifecycle','Privacy, security and support escalation options'];
    content.innerHTML = `<div class="hero-line"><div><p class="eyebrow">${app.label || 'RIDEHUB'} PORTAL · MODULE</p><h1>${escape(title)}</h1><p>${escape(detail)}</p></div><span class="development-pill">UNDER DEVELOPMENT</span></div><div class="dashboard-grid"><article class="card wide-card"><div class="feature-header"><span class="feature-icon">${icon[key] || '◈'}</span><div><h2>${escape(title)}</h2><p>Frontend design is complete; data and actions are intentionally not connected yet.</p></div></div><div class="feature-grid">${safeguards.map((item,i) => `<div class="feature-option"><b>${['Planned workflow','Edge-case coverage','Safe action states'][i]}</b><span>${item}</span></div>`).join('')}</div><div class="notice-bar" style="margin-top:17px">◷ This module is in UI preview mode. No updates, payments, approvals, or data changes can be made from this screen.</div></article><article class="card side-card"><div class="empty-state"><div><div class="empty-icon">${icon[key] || '◈'}</div><h2>Ready for integration</h2><p>Tables, empty states, loading states, validation and service connections will be added when implementation begins.</p><button class="ghost-button" data-page="overview" style="margin-top:16px">Back to overview</button></div></div></article><article class="card full-card"><div class="card-head"><div><h2>Module state</h2><p>Designed to handle normal, empty, pending, declined, cancelled and restricted situations.</p></div></div><div class="progress"><i></i></div></article></div>`;
  };
  const escape = value => String(value || '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  function renderNav(){ nav.innerHTML = current.groups.map(([group,items]) => `<div class="nav-group">${group}</div>${items.map(([key,label]) => `<button class="nav-item ${key === currentPage ? 'active' : ''}" data-page="${key}"><span class="nav-icon">${icon[key] || '◈'}</span>${label}</button>`).join('')}`).join(''); }
  function go(page){ currentPage = page; crumb.textContent = titleFor(page); renderNav(); page === 'overview' ? renderOverview() : renderFeature(page); document.querySelector('#portal-sidebar').classList.remove('open'); window.scrollTo({top:0,behavior:'smooth'}); }
  document.addEventListener('click', event => { const page = event.target.closest('[data-page]')?.dataset.page; if(page) go(page); const notice = event.target.closest('[data-coming-soon]')?.dataset.comingSoon; if(notice) showToast(notice); });
  document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('#portal-sidebar').classList.toggle('open'));
  document.querySelector('#profile-shortcut').addEventListener('click', () => go('profile'));
  document.querySelector('#logout-button').addEventListener('click', async () => { try { await fetch('/api/auth/logout/', {method:'POST',headers:{'X-CSRFToken':app.csrf}}); } finally { window.location.assign('/auth/'); } });
  go('overview');
})();
