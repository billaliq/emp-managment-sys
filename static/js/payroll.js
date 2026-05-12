// static/js/payroll.js
document.addEventListener('DOMContentLoaded', function() {
  // CSRF helper
  function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }
  const csrftoken = getCookie('csrftoken');

  function apiFetch(url, opts = {}) {
    opts.headers = opts.headers || {};
    if (!opts.headers['X-CSRFToken'] && csrftoken) opts.headers['X-CSRFToken'] = csrftoken;
    if (!opts.headers['Accept']) opts.headers['Accept'] = 'application/json';
    return fetch(url, opts).then(async resp => {
      const text = await resp.text();
      let json = {};
      try { json = text ? JSON.parse(text) : {}; } catch (e) { json = { text }; }
      if (!resp.ok) throw json;
      return json;
    });
  }

  // DOM refs
  const payrollTableBody = document.querySelector('#payrollTable tbody');
  const processPayrollBtn = document.getElementById('processPayrollBtn');
  const processPayrollModal = document.getElementById('processPayrollModal');
  const closePayrollModal = document.getElementById('closePayrollModal');
  const cancelPayrollBtn = document.getElementById('cancelPayrollBtn');
  const payrollForm = document.getElementById('payrollForm');
  const viewPayrollModal = document.getElementById('viewPayrollModal');
  const viewPayrollContent = document.getElementById('viewPayrollContent');
  const closeViewPayrollModal = document.getElementById('closeViewPayrollModal');
  const editPayrollModal = document.getElementById('editPayrollModal');
  const editPayrollForm = document.getElementById('editPayrollForm');
  const editRecordId = document.getElementById('editRecordId');
  const editBase = document.getElementById('editBase');
  const editAllowances = document.getElementById('editAllowances');
  const editDeductions = document.getElementById('editDeductions');
  const editNet = document.getElementById('editNet');
  const editStatus = document.getElementById('editStatus');
  const closeEditPayrollModal = document.getElementById('closeEditPayrollModal');
  const exportPayrollCsv = document.getElementById('exportPayrollCsv');

  function formatMoney(v) {
    const n = parseFloat(v || 0);
    if (isNaN(n)) return '0.00';
    return n.toFixed(2);
  }

  function makeRow(rec) {
    const tr = document.createElement('tr');
    tr.dataset.recordId = rec.id;
    tr.innerHTML = `
      <td>${rec.employee_name}</td>
      <td>PKR ${formatMoney(rec.base_salary)}</td>
      <td>PKR ${formatMoney(rec.allowances)}</td>
      <td>PKR ${formatMoney(rec.deductions)}</td>
      <td>PKR ${formatMoney(rec.net_salary)}</td>
      <td>${rec.pay_date}</td>
      <td><span class="badge ${rec.status === 'paid' ? 'success' : rec.status === 'pending' ? 'warning' : ''}">${rec.status}</span></td>
      <td>
        <button class="btn small" data-action="view">View</button>
        <button class="btn small" data-action="edit">Edit</button>
      </td>
    `;
    return tr;
  }

  // Load payrolls from API
  function loadPayrolls() {
    apiFetch(API.getPayrolls).then(json => {
      payrollTableBody.innerHTML = '';
      (json.records || []).forEach(rec => {
        payrollTableBody.appendChild(makeRow(rec));
      });
    }).catch(err => {
      console.error('Error loading payrolls', err);
      payrollTableBody.innerHTML = '<tr><td colspan="8">Failed to load payrolls.</td></tr>';
    });
  }

  // Click action delegation
  document.querySelector('#payrollTable').addEventListener('click', function(e) {
    const btn = e.target.closest('button');
    if (!btn) return;
    const action = btn.dataset.action;
    const tr = btn.closest('tr');
    if (!tr) return;
    const recId = tr.dataset.recordId;

    if (action === 'view') {
      viewPayrollContent.innerHTML = `
        <p><strong>Employee:</strong> ${tr.cells[0].innerText}</p>
        <p><strong>Base Salary:</strong> ${tr.cells[1].innerText}</p>
        <p><strong>Allowances:</strong> ${tr.cells[2].innerText}</p>
        <p><strong>Deductions:</strong> ${tr.cells[3].innerText}</p>
        <p><strong>Net Salary:</strong> ${tr.cells[4].innerText}</p>
        <p><strong>Pay Date:</strong> ${tr.cells[5].innerText}</p>
        <p><strong>Status:</strong> ${tr.cells[6].innerText}</p>
      `;
      viewPayrollModal.classList.add('active');
    } else if (action === 'edit') {
      editRecordId.value = recId;
      editBase.value = tr.cells[1].innerText.replace(/[^0-9.-]/g,'');
      editAllowances.value = tr.cells[2].innerText.replace(/[^0-9.-]/g,'');
      editDeductions.value = tr.cells[3].innerText.replace(/[^0-9.-]/g,'');
      editNet.value = tr.cells[4].innerText.replace(/[^0-9.-]/g,'');
      editStatus.value = tr.cells[6].innerText.trim().toLowerCase();
      editPayrollModal.classList.add('active');
    }
  });

  // Edit save
  editPayrollForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const id = editRecordId.value;
    const payload = {
      base_salary: editBase.value || 0,
      allowances: editAllowances.value || 0,
      deductions: editDeductions.value || 0,
      status: editStatus.value
    };
    const updateUrl = API.updateRecord0.replace('/0/', '/' + id + '/');
    apiFetch(updateUrl, {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: { 'Content-Type': 'application/json' }
    }).then(resp => {
      editPayrollModal.classList.remove('active');
      loadPayrolls();
      alert('Record updated');
    }).catch(err => {
      console.error(err);
      alert('Failed to update');
    });
  });

  // Show/hide modals
  if (processPayrollBtn) processPayrollBtn.addEventListener('click', () => processPayrollModal.classList.add('active'));
  if (closePayrollModal) closePayrollModal.addEventListener('click', () => processPayrollModal.classList.remove('active'));
  if (cancelPayrollBtn) cancelPayrollBtn.addEventListener('click', () => processPayrollModal.classList.remove('active'));
  if (closeViewPayrollModal) closeViewPayrollModal.addEventListener('click', () => viewPayrollModal.classList.remove('active'));
  if (closeEditPayrollModal) closeEditPayrollModal.addEventListener('click', () => editPayrollModal.classList.remove('active'));
  if (document.getElementById('cancelEditPayrollBtn')) document.getElementById('cancelEditPayrollBtn').addEventListener('click', () => editPayrollModal.classList.remove('active'));

  // Process payroll form submit
  payrollForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const payPeriod = document.getElementById('payPeriod').value;
    const payDate = document.getElementById('payDate').value;
    const sel = document.getElementById('payEmployees');
    const selected = Array.from(sel.selectedOptions).map(o => o.value);

    apiFetch(API.processPayroll, {
      method: 'POST',
      body: JSON.stringify({
        pay_period: payPeriod,
        pay_date: payDate,
        employees: selected
      }),
      headers: { 'Content-Type': 'application/json' }
    }).then(resp => {
      processPayrollModal.classList.remove('active');
      loadPayrolls();
      alert('Payroll processed: ' + (resp.created || 0) + ' records created.');
    }).catch(err => {
      console.error(err);
      alert('Failed to process payroll');
    });
  });

  // Export CSV
  if (exportPayrollCsv) {
    exportPayrollCsv.addEventListener('click', function() {
      const rows = Array.from(document.querySelectorAll('#payrollTable tr'));
      const csv = rows.map(r => Array.from(r.querySelectorAll('th, td')).map(c => `"${c.innerText.replace(/"/g,'""')}"`).join(',')).join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'payroll.csv';
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  // Initial load
  loadPayrolls();
});
