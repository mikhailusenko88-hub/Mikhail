const id = (location.href.match(/item_id=(\d+)/) || [])[1];
const h = id ? await (await fetch('/' + id, {credentials: 'include'})).text() : '';
const d = new DOMParser().parseFromString(h, 'text/html');
({url: location.href.slice(0, 110), id, title: (d.querySelector('h1') || {}).textContent, price: (h.match(/itemprop="price" content="(\d+)"/) || h.match(/"price":(\d+)/) || [])[1],
  desc: h.includes('срок поставки'), params: [...d.querySelectorAll('[data-marker="item-view/item-params"] li')].map(li => li.textContent.trim()).join('; '),
  addr: ((d.querySelector('[itemprop="address"]') || {}).textContent || '').slice(0, 30), log: JSON.parse(sessionStorage.getItem('nd_log') || '[]').slice(-4)})
