/* DormDrop frontend. Plain JavaScript, one init function per page (selected by <body data-page>).
 * Every value that comes from the API and ends up in HTML goes through escapeHtml(). */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
// Set window.DORMDROP_API_BASE before this script if the API is hosted on a different origin.
const API_BASE = window.DORMDROP_API_BASE || '';
const token = () => localStorage.getItem('dd_token');
const currentUser = () => JSON.parse(localStorage.getItem('dd_user') || '{}');
const money = amount => `ZMW ${Number(amount || 0).toFixed(2)}`;
const categories = [
  {name:'Food', label:'Food & drinks', image:'/static/images/food.jpg', alt:'Groceries and drinks'},
  {name:'Clothing', label:'Clothing', image:'/static/images/clothes.jpg', alt:'Clothing'},
  {name:'Shoes', label:'Shoes & footwear', image:'https://images.unsplash.com/photo-1560769629-975ec94e6a86?auto=format&fit=crop&w=900&q=85', alt:'Shoes'},
  {name:'Electronics', label:'Electronics', image:'/static/images/electronics.jpg', alt:'Electronics'},
  {name:'Furniture', label:'Furniture', image:'/static/images/furniture.jpg', alt:'Furniture'},
  {name:'Personal Care', label:'Personal care', image:'/static/images/personal-care.jpg', alt:'Personal care products'},
  {name:'Stationery', label:'Stationery', image:'/static/images/stationery.jpg', alt:'Stationery'},
  {name:'Bags & Backpacks', label:'Bags & backpacks', image:'https://valenciacollege.edu/students/campus-store/images/campus-store-east-134142.jpeg', alt:'Backpacks in a campus store'},
  {name:'Dorm Essentials', label:'Dorm essentials', image:'https://images.unsplash.com/photo-1555930112-0159bcdc3fe5?auto=format&fit=crop&w=900&q=85', alt:'Student room essentials'},
  {name:'Cleaning & Laundry', label:'Cleaning & laundry', image:'https://images.unsplash.com/photo-1528740561666-dc2479dc08ab?auto=format&fit=crop&w=900&q=85', alt:'Household cleaning supplies'},
  {name:'Kitchenware', label:'Kitchenware', image:'https://images.unsplash.com/photo-1779457524854-208563209eea?auto=format&fit=crop&w=900&q=85', alt:'Kitchen utensils and cooking essentials'},
  {name:'Sports & Fitness', label:'Sports & fitness', image:'/static/images/image102.jpg', alt:'Football and sports'},
  {name:'Books', label:'Books & study guides', image:'https://images.unsplash.com/photo-1629652487043-fb2825838f8c?auto=format&fit=crop&w=900&q=85', alt:'Books and study materials'}
];

function renderCategories() {
  ['home-categories', 'browse-categories'].forEach(id => {
    const root = document.getElementById(id);
    if (!root) return;
    root.innerHTML = categories.map(category =>
      `<a class="category-card" href="/static/category.html?category=${encodeURIComponent(category.name)}"><img src="${escapeHtml(category.image)}" alt="${escapeHtml(category.alt)}" loading="lazy"><span>${escapeHtml(category.label)}</span></a>`
    ).join('');
  });
}

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, options = {}) {
  const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(API_BASE + path, {...options, headers});
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({detail: 'Unexpected server response'}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : data.detail;
    throw new ApiError(detail || 'Request failed', response.status);
  }
  return data;
}

function notice(text, kind = 'info') {
  const box = $('#notice');
  if (box) { box.textContent = text; box.className = `notice ${kind}`; }
}

/** Run an async action, showing any error in the notice box. Returns undefined on failure. */
async function attempt(action) {
  try { return await action(); } catch (err) { notice(err.message, 'error'); }
}

function formData(form) { return Object.fromEntries(new FormData(form)); }

function renderNav() {
  const el = $('#account-nav');
  if (!el) return;
  const user = currentUser();
  el.innerHTML = token()
    ? `<a href="/static/chat.html">Messages</a>${user.account_type === 'seller' ? '<a href="/static/seller-dashboard.html">Seller studio</a>' : ''}` +
      `${user.is_admin ? '<a href="/static/admin-dashboard.html">Admin</a>' : ''}<button class="quiet" id="logout">Log out</button>`
    : '<a href="/">Sign in</a>';
  $('#logout')?.addEventListener('click', () => { localStorage.clear(); location.href = '/'; });
}

function imageTag(url, alt = '') {
  return url ? `<img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}">` : '';
}

function categoryImage(category) {
  return categories.find(x => x.name.toLowerCase() === String(category || '').toLowerCase())?.image || '/static/images/image7.jpg';
}

const card = item => `<a class="item-card" href="/static/listing.html?id=${Number(item.id)}">` +
  `<div class="item-image">${imageTag(item.images?.[0]?.url || categoryImage(item.category), item.title)}</div>` +
  `<div class="item-info"><span class="eyebrow">${escapeHtml(item.category)}</span><h3>${escapeHtml(item.title)}</h3>` +
  `<b>${money(item.price)}</b><small>${Number(item.quantity)} available</small></div></a>`;

/* ------------------------------------------------------------------ auth */
async function initAuth() {
  const type = $('#signup-type');
  const buyerFields = $('#buyer-signup-fields');
  const sellerFields = $('#seller-signup-fields');
  function syncSignupType() {
    const isSeller = type ? type.value === 'seller' : document.body.dataset.page === 'seller-register';
    if (buyerFields) {
      buyerFields.hidden = isSeller;
      $$('input,select,textarea', buyerFields).forEach(field => { field.disabled = isSeller; });
    }
    if (sellerFields) {
      sellerFields.hidden = !isSeller;
      $$('input,select,textarea', sellerFields).forEach(field => { field.disabled = !isSeller; });
    }
    const email = $('#signup-form [name="email"]');
    if (email) email.placeholder = isSeller ? 'supplier@yourcompany.com' : 'you@university.edu';
  }
  type?.addEventListener('change', syncSignupType);
  syncSignupType();
  $('#login-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    await attempt(async () => {
      const data = await api('/auth/login', {method: 'POST', body: JSON.stringify(formData(e.currentTarget))});
      localStorage.setItem('dd_token', data.access_token);
      localStorage.setItem('dd_user', JSON.stringify(data.user));
      location.href = '/static/marketplace.html';
    });
  });
  $('#signup-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    await attempt(async () => {
      const data = await api('/auth/signup', {method: 'POST', body: JSON.stringify(formData(e.currentTarget))});
      $('#verify-token').value = data.verification_token;
      $('#verify-token').closest('details')?.setAttribute('open', '');
      notice(data.account_type === 'seller'
        ? 'Seller account created. Verify your email, then request seller approval from Seller Studio.'
        : 'Buyer account created. Your development verification token is ready below.', 'success');
    });
  });
  $('#verify-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    await attempt(async () => {
      await api('/auth/verify', {method: 'POST', body: JSON.stringify({token: $('#verify-token').value})});
      notice(document.body.dataset.page === 'seller-register'
        ? 'Email verified. Your supplier profile now appears in Partners. Sign in to request seller approval.'
        : 'Email verified. You can now sign in.', 'success');
    });
  });
}

/* ------------------------------------------------------------ marketplace */
async function initMarketplace() {
  const form = $('#filters');
  async function load() {
    await attempt(async () => {
      const query = new URLSearchParams([...new FormData(form)].filter(([, value]) => String(value).trim() !== ''));
      const listings = await api(`/listings?${query}`);
      $('#listing-grid').innerHTML = listings.map(card).join('') || '<p class="empty">No approved listings match those filters.</p>';
    });
  }
  const params = new URLSearchParams(location.search);
  if (params.has('category')) form.elements.category.value = params.get('category');
  form?.addEventListener('submit', e => { e.preventDefault(); load(); });
  $$('[data-category]').forEach(button => button.addEventListener('click', () => {
    form.elements.category.value = button.dataset.category;
    load();
    $('#products').scrollIntoView({behavior: 'smooth'});
  }));
  await load();
}

async function initCategoryPage() {
  const name = new URLSearchParams(location.search).get('category') || '';
  const category = categories.find(item => item.name.toLowerCase() === name.toLowerCase());
  if (!category) return notice('Choose a category from the marketplace to browse its listings.', 'error');
  $('#category-title').textContent = category.label;
  $('#category-image').src = category.image;
  $('#category-image').alt = category.alt;
  $('#category-name').textContent = category.name;
  const listings = await attempt(() => api(`/listings?category=${encodeURIComponent(category.name)}`));
  if (listings) $('#listing-grid').innerHTML = listings.map(card).join('') || '<p class="empty">There are no approved listings in this category yet.</p>';
}

async function initPartners() {
  const partners = await attempt(() => api('/partners'));
  if (!partners) return;
  $('#partners-grid').innerHTML = partners.map(partner => {
    const mark = String(partner.business_name || 'Partner').trim().split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase();
    return `<article class="partner-card"><div class="partner-mark">${escapeHtml(mark)}</div>` +
      `<span class="partner-status">${escapeHtml(partner.status)}</span><h3>${escapeHtml(partner.business_name || 'DormDrop supplier')}</h3>` +
      `<p class="partner-location">${escapeHtml(partner.country || 'Location not provided')}</p>` +
      `<p>${escapeHtml(partner.business_description || 'A DormDrop supplier serving campus communities.')}</p>` +
      `<p><b>Products:</b> ${escapeHtml(partner.product_types || 'Product details coming soon')}</p>` +
      `<div class="partner-contact"><span>${escapeHtml(partner.contact_person || 'Supplier contact')}</span>` +
      `<a href="mailto:${escapeHtml(partner.email)}">${escapeHtml(partner.email)}</a>` +
      `${partner.phone ? `<a href="tel:${escapeHtml(partner.phone.replace(/[^+\d]/g, ''))}">${escapeHtml(partner.phone)}</a>` : ''}</div></article>`;
  }).join('') || '<p class="empty partner-empty">No verified suppliers have joined yet. Register as a partner and your profile will appear here after email verification.</p>';
  $('#partner-collections').innerHTML = categories.slice(0, 6).map(category =>
    `<a class="collection-card" href="/static/category.html?category=${encodeURIComponent(category.name)}"><img src="${escapeHtml(category.image)}" alt="${escapeHtml(category.alt)}" loading="lazy"><h3>${escapeHtml(category.label)}</h3><p>Browse supplier listings</p></a>`
  ).join('');
}

async function initListing() {
  const id = new URLSearchParams(location.search).get('id');
  if (!id) return notice('No listing selected', 'error');
  await attempt(async () => {
    const item = await api(`/listings/${encodeURIComponent(id)}`);
    const seller = item.seller;
    $('#detail').innerHTML =
      `<div class="detail-image">${imageTag(item.images?.[0]?.url, item.title) || '<span>DormDrop</span>'}</div>` +
      `<div><span class="eyebrow">${escapeHtml(item.category)}</span><h1>${escapeHtml(item.title)}</h1>` +
      `<p>${escapeHtml(item.description)}</p><h2>${money(item.price)}</h2>` +
      `<p>${Number(item.length_cm)} × ${Number(item.width_cm)} × ${Number(item.height_cm)} cm · ${Number(item.weight_kg)} kg</p>` +
      `<p>Seller #${Number(seller.id)} · ${escapeHtml(seller.campus)} · ${escapeHtml(seller.dorm)} · ★ ${Number(seller.rating_avg).toFixed(1)}</p>` +
      `<label>Quantity <input id="quantity" type="number" min="1" max="${Number(item.quantity)}" value="1"></label>` +
      `<button id="add-cart">Add to cart</button>` +
      `<a class="quiet" href="/static/chat.html?peer=${Number(seller.id)}&listing=${Number(item.id)}">Message seller</a></div>`;
    const reviews = await api(`/sellers/${Number(seller.id)}/reviews`);
    const reviewHtml = reviews.map(r => `<p>★ ${Number(r.rating)} · ${escapeHtml(r.comment)} <small>— ${escapeHtml(r.buyer)}</small></p>`).join('');
    $('#detail').insertAdjacentHTML('afterend',
      `<section class="panel section"><h2>Seller reviews</h2>${reviewHtml || '<p class="muted">No reviews yet.</p>'}</section>`);
    $('#add-cart').addEventListener('click', () => attempt(async () => {
      await api('/cart/items', {method: 'POST', body: JSON.stringify({listing_id: item.id, quantity: Number($('#quantity').value)})});
      notice('Added to your cart', 'success');
    }));
  });
}

/* --------------------------------------------------------------- cart */
async function initCart() {
  await attempt(async () => {
    const cart = await api('/cart');
    $('#cart-items').innerHTML = cart.items.map(x =>
      `<article class="cart-row"><div><b>${escapeHtml(x.title)}</b><small>${money(x.price)} each</small></div>` +
      `<label>Qty <input data-qty="${Number(x.id)}" type="number" min="1" max="${Number(x.available_quantity)}" value="${Number(x.quantity)}"></label>` +
      `<b>${money(x.item_subtotal)}</b><small>Shipping ${money(x.item_shipping_fee)}</small>` +
      `<button class="quiet" data-remove="${Number(x.id)}">Remove</button></article>`).join('') || '<p class="empty">Your cart is empty.</p>';
    $('#subtotal').textContent = money(cart.subtotal);
    $('#shipping').textContent = money(cart.shipping_fee);
    $('#grand-total').textContent = money(cart.grand_total);
    // Always re-render afterwards: on success totals refresh, on failure the input snaps back to the server value.
    $$('[data-qty]').forEach(input => input.onchange = () => attempt(() =>
      api(`/cart/items/${input.dataset.qty}`, {method: 'PUT', body: JSON.stringify({quantity: Number(input.value)})})
    ).then(() => initCart()));
    $$('[data-remove]').forEach(button => button.onclick = () => attempt(async () => {
      await api(`/cart/items/${button.dataset.remove}`, {method: 'DELETE'});
      await initCart();
    }));
  });
}

async function initCheckout() {
  const cart = await attempt(() => api('/cart'));
  if (!cart) return;
  $('#checkout-summary').innerHTML =
    `<p>Items <b>${money(cart.subtotal)}</b></p><p>Shipping <b>${money(cart.shipping_fee)}</b></p>` +
    `<h2>Grand total <strong>${money(cart.grand_total)}</strong></h2>`;
  if (!cart.items.length) {
    notice('Your cart is empty. Add something from the marketplace first.', 'error');
    $('#checkout-form').hidden = true;
    return;
  }
  $('#checkout-form').addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget;
    const submit = $('button', form);
    submit.disabled = true;  // prevents a double click from placing two orders
    const order = await attempt(() => api('/checkout', {method: 'POST', body: JSON.stringify(formData(form))}));
    if (order) {
      notice(`Order ${order.order_id} placed · ${money(order.total)}`, 'success');
      form.hidden = true;
      $('#order-link').innerHTML = '<a class="button" href="/static/orders.html">Track order</a>';
    } else {
      submit.disabled = false;
    }
  });
}

/* ------------------------------------------------------------- orders */
function orderCard(order) {
  const sellerIds = [...new Set(order.items.map(x => x.seller_id).filter(Boolean))];
  const reviewed = new Set(order.reviewed_seller_ids || []);
  const step = (label, statuses) => `<span class="${statuses.includes(order.status) ? 'done' : ''}">${label}</span>`;
  const reviewForms = order.status !== 'delivered' ? '' : sellerIds.filter(id => !reviewed.has(id)).map(id =>
    `<form class="review-form" data-order="${escapeHtml(order.order_id)}" data-seller="${Number(id)}">` +
    `<label>Rate seller #${Number(id)}<select name="rating">${[5, 4, 3, 2, 1].map(n => `<option value="${n}">${n} ★</option>`).join('')}</select></label>` +
    `<input name="comment" placeholder="Write a review"><button>Submit review</button></form>`).join('');
  const chatLinks = sellerIds.map(id =>
    `<a href="/static/chat.html?peer=${Number(id)}&order=${encodeURIComponent(order.order_id)}">Message seller #${Number(id)}</a>`).join(' · ');
  return `<article class="panel order-card"><div class="order-top"><div><span class="eyebrow">${escapeHtml(order.order_id)}</span>` +
    `<h2>${escapeHtml(order.status.replaceAll('_', ' '))}</h2></div><b>${money(order.total)}</b></div>` +
    `<div class="steps ${escapeHtml(order.status)}">${step('Picked Up', ['picked_up', 'in_transit', 'delivered'])}<i></i>` +
    `${step('In Transit', ['in_transit', 'delivered'])}<i></i>${step('Delivered', ['delivered'])}</div>` +
    `<p>Items ${money(order.subtotal)} · Shipping ${money(order.shipping_fee)}</p><p>${chatLinks}</p>${reviewForms}</article>`;
}

async function initOrders() {
  await attempt(async () => {
    const orders = await api('/orders');
    $('#orders').innerHTML = orders.map(orderCard).join('') || '<p class="empty">Your orders will appear here.</p>';
    $$('.review-form').forEach(form => form.onsubmit = async e => {
      e.preventDefault();
      const data = {...formData(form), order_id: form.dataset.order, seller_id: Number(form.dataset.seller)};
      const saved = await attempt(() => api('/reviews', {method: 'POST', body: JSON.stringify(data)}));
      if (saved) { notice('Thank you for your review', 'success'); form.remove(); }
    });
  });
}

/* ------------------------------------------------------------- seller */
function listingRow(x) {
  return `<div class="table-row"><div><b>${escapeHtml(x.title)}</b><small>${escapeHtml(x.status)} · ${Number(x.quantity)} in stock</small></div>` +
    `<b>${money(x.price)}</b><button class="quiet" data-edit-listing="${Number(x.id)}">Edit</button>` +
    `${x.status !== 'sold' ? `<button class="quiet" data-sold-listing="${Number(x.id)}">Mark sold</button>` : ''}` +
    `<button class="quiet" data-delete-listing="${Number(x.id)}">Delete</button></div>`;
}

const NEXT_STATUS = {awaiting_pickup: 'picked_up', picked_up: 'in_transit', in_transit: 'delivered'};

function saleRow(x) {
  const next = x.can_advance ? NEXT_STATUS[x.status] : null;
  return `<div class="table-row"><b>${escapeHtml(x.order_id)}</b><span>${escapeHtml(x.status)}</span><span>${Number(x.quantity)} sold</span>` +
    `<b>${money(x.gross)}</b>${next ? `<button data-seller-advance="${escapeHtml(x.order_id)}" data-next-status="${next}">Mark ${next.replace('_', ' ')}</button>` : ''}</div>`;
}

/** Rebuilds the dashboard. Safe to call repeatedly: it never attaches handlers to the static forms. */
async function renderSeller() {
  let data, admin;
  try {
    data = await api('/seller/dashboard');
    admin = await api('/seller/admin-contact');
  } catch (err) {
    // Buyer and seller accounts stay separate. Only seller accounts can request approval.
    if (err.status !== 403) notice(err.message, 'error');
    const sellerAccount = currentUser().account_type === 'seller';
    $('#seller-request-panel').hidden = !sellerAccount;
    $('#buyer-role-message').hidden = sellerAccount;
    $('#listing-form').closest('.panel').hidden = true;
    return;
  }
  $('#seller-request-panel').hidden = true;
  $('#buyer-role-message').hidden = true;
  $('#listing-form').closest('.panel').hidden = false;
  $('#seller-summary').innerHTML =
    `<div><b>${data.listings.length}</b><small>Listings</small></div><div><b>${money(data.gross_sales)}</b><small>Gross sales</small></div>` +
    `<div><b>${money(data.revenue_after_commission)}</b><small>After commission</small></div>` +
    `<div><b>${money(data.available_for_payout)}</b><small>Available for payout · ${money(data.paid_out)} paid out</small></div>` +
    `<div><a class="button" href="/static/chat.html?peer=${Number(admin.id)}">Chat with admin</a></div>`;
  $('#seller-listings').innerHTML = data.listings.map(listingRow).join('') || '<p>No listings yet.</p>';
  $('#seller-sales').innerHTML = data.sales.map(saleRow).join('') || '<p>No sales yet.</p>';

  $$('[data-edit-listing]').forEach(button => button.onclick = () => attempt(async () => {
    const listing = data.listings.find(v => v.id === Number(button.dataset.editListing));
    const title = prompt('Listing title', listing.title);
    if (title === null) return;
    const price = Number(prompt('Price in ZMW', listing.price));
    if (!price) return;
    await api(`/listings/${listing.id}`, {method: 'PUT', body: JSON.stringify({...listing, title, price, images: listing.images})});
    notice('Changes submitted for approval', 'success');
    await renderSeller();
  }));
  $$('[data-sold-listing]').forEach(button => button.onclick = () => attempt(async () => {
    await api(`/listings/${button.dataset.soldListing}/sold`, {method: 'POST'});
    notice('Listing marked sold', 'success');
    await renderSeller();
  }));
  $$('[data-delete-listing]').forEach(button => button.onclick = () => attempt(async () => {
    if (!confirm('Delete this listing?')) return;
    await api(`/listings/${button.dataset.deleteListing}`, {method: 'DELETE'});
    notice('Listing deleted', 'success');
    await renderSeller();
  }));
  $$('[data-seller-advance]').forEach(button => button.onclick = () => attempt(async () => {
    await api(`/admin/orders/${encodeURIComponent(button.dataset.sellerAdvance)}/status`,
              {method: 'PUT', body: JSON.stringify({status: button.dataset.nextStatus})});
    notice('Order status updated', 'success');
    await renderSeller();
  }));
}

async function initSeller() {
  // Bound once here, not in renderSeller(), so a refresh cannot stack duplicate submit handlers.
  $('#seller-request-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    await attempt(async () => {
      await api('/seller-requests', {method: 'POST'});
      notice('Seller request submitted for admin review', 'success');
    });
  });
  $('#listing-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const form = e.currentTarget;
    const d = formData(form);
    for (const key of ['price', 'length_cm', 'width_cm', 'height_cm', 'weight_kg', 'quantity']) d[key] = Number(d[key]);
    d.images = d.image ? [d.image] : [];
    delete d.image;
    const saved = await attempt(() => api('/listings', {method: 'POST', body: JSON.stringify(d)}));
    if (saved) {
      notice('Listing submitted for admin approval', 'success');
      form.reset();
      await renderSeller();
    }
  });
  await renderSeller();
}

/* -------------------------------------------------------------- admin */
async function adminAction(path) {
  const done = await attempt(() => api(path, {method: 'POST'}));
  if (done) { notice('Updated successfully', 'success'); await renderAdmin(); }
}

async function editListingAsAdmin(listing) {
  const title = prompt('Listing title', listing.title);
  if (title === null) return;
  const price = Number(prompt('Price in ZMW', listing.price));
  if (!price) return;
  const saved = await attempt(() => api(`/admin/listings/${listing.id}`,
    {method: 'PUT', body: JSON.stringify({...listing, title, price, images: listing.images.map(i => i.url)})}));
  if (saved) { notice('Listing updated', 'success'); await renderAdmin(); }
}

function adminListingRows(listings, withActions) {
  return listings.map(x => withActions
    ? `<article class="table-row"><div><b>${escapeHtml(x.title)}</b><small>${escapeHtml(x.category)} · ${money(x.price)}</small></div>` +
      `<button class="quiet" data-admin-edit="${Number(x.id)}">Edit title/price</button><button data-approve="${Number(x.id)}">Approve</button>` +
      `<button class="quiet" data-disapprove="${Number(x.id)}">Disapprove</button></article>`
    : `<div class="table-row"><span>${escapeHtml(x.title)}</span><span>${escapeHtml(x.status)}</span><b>${money(x.price)}</b>` +
      `<button class="quiet" data-edit-any-listing="${Number(x.id)}">Edit</button></div>`).join('');
}

function adminUserRow(x) {
  const actions = x.is_admin ? '' :
    `${x.is_seller ? `<a href="/static/chat.html?peer=${Number(x.id)}">Message</a>` : ''}` +
    `<button class="quiet" data-user-id="${Number(x.id)}" data-action="${x.is_suspended ? 'unsuspend' : 'suspend'}">${x.is_suspended ? 'Unsuspend' : 'Suspend'}</button>`;
  return `<div class="table-row"><span>#${Number(x.id)} · ${escapeHtml(x.email)}</span><span>${x.account_type === 'admin' ? 'Admin' : x.account_type === 'seller' ? 'Seller' : 'Buyer'}</span>` +
    `<span>${x.is_suspended ? 'Suspended' : 'Active'}</span>${actions}</div>`;
}

async function renderAdmin() {
  const load = async (path, fallback) => { try { return await api(path); } catch (e) { notice(e.message, 'error'); return fallback; } };
  const [pending, listings, requests, users, orders, commissions] = await Promise.all([
    load('/admin/listings/pending', []), load('/admin/listings', []), load('/admin/seller-requests', []),
    load('/admin/users', []), load('/admin/orders', []), load('/admin/commissions', null)]);

  if (commissions) {
    $('#commission-summary').innerHTML = `<h2>${money(commissions.total_earnings)}</h2><p>Total commission · ${(commissions.commission_rate * 100).toFixed(1)}%</p>`;
    $('#commission-rows').innerHTML = commissions.entries.map(x => `<div class="table-row"><b>${escapeHtml(x.order_id)}</b><span>Commission ${money(x.amount)}</span></div>`).join('') || '<p>No commissions yet.</p>';
    $('#payout-rows').innerHTML = commissions.payouts.map(x => `<div class="table-row"><span>Seller #${Number(x.seller_id)} · ${escapeHtml(x.reference)}</span><b>${money(x.amount)}</b></div>`).join('') || '<p>No payouts recorded.</p>';
  }
  $('#pending-listings').innerHTML = adminListingRows(pending, true) || '<p>No listings waiting for review.</p>';
  $('#all-listings').innerHTML = adminListingRows(listings, false) || '<p>No listings exist.</p>';
  $('#seller-requests').innerHTML = requests.map(x => `<div class="table-row"><div><b>${escapeHtml(x.business_name || x.email)}</b><small>${escapeHtml(x.contact_person || 'Contact not provided')} · ${escapeHtml(x.phone || 'Phone not provided')} · ${escapeHtml(x.country || 'Country not provided')} · ${escapeHtml(x.email)}</small><small>${escapeHtml(x.product_types || 'Products not specified')} · ${escapeHtml(x.business_description || '')}</small></div><span>${escapeHtml(x.status)}</span>` +
    `${x.status === 'pending' ? `<button data-seller-approve="${Number(x.id)}">Approve seller</button><button class="quiet" data-seller-reject="${Number(x.id)}">Reject</button>` : ''}</div>`).join('') || '<p>No seller requests.</p>';
  $('#admin-users').innerHTML = users.map(adminUserRow).join('') || '<p>No users found.</p>';
  $('#admin-orders').innerHTML = orders.map(x => {
    const next = NEXT_STATUS[x.status];
    return `<div class="table-row"><b>${escapeHtml(x.order_id)}</b><span>${escapeHtml(x.status)}</span><b>${money(x.total)}</b>` +
      `${next ? `<button data-advance-order="${escapeHtml(x.order_id)}" data-next-status="${next}">Mark ${next.replace('_', ' ')}</button>` : ''}</div>`;
  }).join('') || '<p>No orders yet.</p>';

  $$('[data-admin-edit]').forEach(b => b.onclick = () => editListingAsAdmin(pending.find(v => v.id === Number(b.dataset.adminEdit))));
  $$('[data-edit-any-listing]').forEach(b => b.onclick = () => editListingAsAdmin(listings.find(v => v.id === Number(b.dataset.editAnyListing))));
  $$('[data-approve]').forEach(b => b.onclick = () => adminAction(`/admin/listings/${b.dataset.approve}/approve`));
  $$('[data-disapprove]').forEach(b => b.onclick = () => adminAction(`/admin/listings/${b.dataset.disapprove}/disapprove`));
  $$('[data-seller-approve]').forEach(b => b.onclick = () => adminAction(`/admin/seller-requests/${b.dataset.sellerApprove}/approve`));
  $$('[data-seller-reject]').forEach(b => b.onclick = () => adminAction(`/admin/seller-requests/${b.dataset.sellerReject}/reject`));
  $$('[data-user-id]').forEach(b => b.onclick = () => adminAction(`/admin/users/${b.dataset.userId}/${b.dataset.action}`));
  $$('[data-advance-order]').forEach(b => b.onclick = () => attempt(async () => {
    await api(`/admin/orders/${encodeURIComponent(b.dataset.advanceOrder)}/status`, {method: 'PUT', body: JSON.stringify({status: b.dataset.nextStatus})});
    notice('Order status updated', 'success');
    await renderAdmin();
  }));
}

async function initAdmin() {
  // Bound once so refreshing the page data cannot record a payout twice.
  $('#payout-form')?.addEventListener('submit', async e => {
    e.preventDefault();
    const d = formData(e.currentTarget);
    d.seller_id = Number(d.seller_id);
    d.amount = Number(d.amount);
    const saved = await attempt(() => api('/admin/payouts', {method: 'POST', body: JSON.stringify(d)}));
    if (saved) { notice('Seller payout recorded', 'success'); await renderAdmin(); }
  });
  await renderAdmin();
}

/* --------------------------------------------------------------- chat */
async function initChat() {
  const params = new URLSearchParams(location.search);
  $('#peer').value = params.get('peer') || '';
  $('#listing-context').value = params.get('listing') || '';
  $('#order-context').value = params.get('order') || '';

  async function loadMessages() {
    const peer = $('#peer').value;
    if (!peer) return;
    await attempt(async () => {
      const context = new URLSearchParams();
      if ($('#listing-context').value) context.set('listing_id', $('#listing-context').value);
      if ($('#order-context').value) context.set('order_id', $('#order-context').value);
      const messages = await api(`/messages/${encodeURIComponent(peer)}?${context}`);
      const me = Number(currentUser().id);
      $('#chat-log').innerHTML = messages.map(x =>
        `<div class="bubble ${x.sender_id === me ? 'mine' : ''}">${escapeHtml(x.body)}<small>${new Date(x.created_at).toLocaleString()}</small></div>`).join('')
        || '<p class="muted">No messages yet. Say hello below.</p>';
      $('#chat-log').scrollTop = $('#chat-log').scrollHeight;
    });
  }

  async function loadInbox() {
    const inbox = await attempt(() => api('/messages'));
    if (!inbox) return;
    $('#conversations').innerHTML = inbox.map(c =>
      `<button type="button" class="quiet" data-peer="${Number(c.peer_id)}">${escapeHtml(c.peer_label)}<small>${escapeHtml(c.last_message)}</small></button>`).join('')
      || '<p class="muted">No conversations yet.</p>';
    $$('[data-peer]').forEach(button => button.onclick = () => {
      $('#peer').value = button.dataset.peer;
      $('#listing-context').value = '';  // an existing thread needs no extra context
      $('#order-context').value = '';
      loadMessages();
    });
  }

  $('#load-chat').onclick = loadMessages;
  $('#chat-form').onsubmit = async e => {
    e.preventDefault();
    const d = formData(e.currentTarget);
    d.receiver_id = Number($('#peer').value);
    d.listing_id = d.listing_id ? Number(d.listing_id) : null;
    d.order_id = d.order_id || null;
    const sent = await attempt(() => api('/messages', {method: 'POST', body: JSON.stringify(d)}));
    if (sent) { $('#message-body').value = ''; await loadMessages(); await loadInbox(); }
  };
  await loadInbox();
  if ($('#peer').value) await loadMessages();
}

document.addEventListener('DOMContentLoaded', () => {
  renderCategories();
  renderNav();
  const pages = {auth: initAuth, marketplace: initMarketplace, listing: initListing, cart: initCart, checkout: initCheckout,
                 orders: initOrders, seller: initSeller, admin: initAdmin, chat: initChat, category: initCategoryPage,
                 'seller-register': initAuth, partners: initPartners};
  const init = pages[document.body.dataset.page];
  if (init) init().catch(e => notice(e.message, 'error'));
});

