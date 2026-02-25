const dropArea = document.getElementById('drop-area');
const fileInput = document.getElementById('file-input');
const statusMessage = document.getElementById('status-message');
const resultsSection = document.getElementById('results-section');
const statsEl = document.getElementById('stats');
const tableHead = document.getElementById('table-head');
const tableBody = document.getElementById('table-body');
const alertMessage = document.getElementById('alert-message');
const exportCsvBtn = document.getElementById('export-csv');
const exportXlsxBtn = document.getElementById('export-xlsx');
const printBtn = document.getElementById('print-report');
const embarqueFilter = document.getElementById('embarque-filter');
const printArea = document.getElementById('print-area');

// Elementos do Modal
const errorModal = document.getElementById('error-modal');
const errorLogContainer = document.getElementById('error-log-container');
const closeModalBtns = [document.getElementById('close-modal'), document.getElementById('modal-close-btn')];

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
let parsedData = [];
let allEmbarques = new Set();
let currentFilter = 'all';
let failedLinesLog = [];

// Colunas unificadas
const columns = [
    "Embarque", "Cliente", "Pedido", "Ped. Cliente", "Dep", "Emit", "Tipo",
    "Representante", "Previsão", "Data Pedido", "Item", "Descrição",
    "Unidade", "Qt Alocada", "Qt Embalagem", "Peso Total", "Cubagem"
];

// Eventos
['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) { e.preventDefault(); e.stopPropagation(); }

['dragenter', 'dragover'].forEach(eventName => {
    dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'), false);
});

dropArea.addEventListener('drop', handleDrop, false);
fileInput.addEventListener('change', handleFileSelect, false);

exportCsvBtn.addEventListener('click', () => exportData('csv'));
exportXlsxBtn.addEventListener('click', () => exportData('xlsx'));
printBtn.addEventListener('click', generatePrintReport);

embarqueFilter.addEventListener('change', (e) => {
    currentFilter = e.target.value;
    renderTable();
});

closeModalBtns.forEach(btn => btn.addEventListener('click', () => errorModal.classList.add('hidden')));

function openErrorModal() {
    if (failedLinesLog.length === 0) return;
    errorLogContainer.innerHTML = '';
    failedLinesLog.forEach((line) => {
        const lineEl = document.createElement('div');
        lineEl.style.padding = '0.5rem 0';
        lineEl.style.borderBottom = '1px solid #374151';
        lineEl.textContent = `[LINHA] ${line}`;
        errorLogContainer.appendChild(lineEl);
    });
    errorModal.classList.remove('hidden');
}

function handleDrop(e) { processFile(e.dataTransfer.files[0]); }
function handleFileSelect(e) { processFile(e.target.files[0]); }

function processFile(file) {
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) { showError('O arquivo excede o limite de 5MB.'); return; }
    showStatus('Lendo arquivo...');
    const reader = new FileReader();
    reader.onload = (e) => analyzeContent(e.target.result);
    reader.readAsText(file, 'ISO-8859-1');
}

function analyzeContent(content) {
    const lines = content.split(/\r?\n/);
    parsedData = [];
    allEmbarques.clear();
    failedLinesLog = [];

    let ctx = { embarque: 'N/I', cliente: 'N/I', pedido: '', pedCliente: '', dep: '', emit: '', tipo: '', rep: '', previsao: '', dtPedido: '' };
    let inItemTable = false;

    for (let i = 0; i < lines.length; i++) {
        const rawLine = lines[i];
        const trimmed = rawLine.trim();
        if (trimmed === '') continue;

        const ebMatch = trimmed.match(/Embarque:\s*(\d+)/i);
        if (ebMatch) { ctx.embarque = ebMatch[1]; allEmbarques.add(ctx.embarque); continue; }

        const clMatch = trimmed.match(/Cliente:\s*(.+)$/i);
        if (clMatch) { ctx.cliente = clMatch[1].trim(); continue; }

        if (trimmed.startsWith('Pedido') && trimmed.includes('Representante')) {
            inItemTable = false;
            if (lines[i + 2]) parsePedidoLine(lines[i + 2], ctx);
            i += 2; continue;
        }

        if (trimmed.startsWith('Item') && trimmed.includes('Descrição')) {
            inItemTable = true; i++; continue;
        }

        if (inItemTable && /^\d+/.test(trimmed)) {
            const item = parseItemLine(rawLine, ctx);
            if (item) parsedData.push(item); else failedLinesLog.push(rawLine);
            continue;
        }

        if (trimmed.includes('DATASUL') || trimmed.includes('Página:')) inItemTable = false;
    }

    setupEmbarqueFilter();
    renderTable();
    showStatus('Pronto.');
}

function parsePedidoLine(line, ctx) {
    const parts = line.trim().split(/\s{2,}/);
    if (parts.length >= 8) {
        ctx.pedido = parts[0]; ctx.pedCliente = parts[1]; ctx.dep = parts[2];
        ctx.emit = parts[3]; ctx.tipo = parts[4]; ctx.rep = parts[5];
        ctx.previsao = parts[6]; ctx.dtPedido = parts[7];
    }
}

function parseItemLine(line, ctx) {
    const parts = line.trim().split(/\s{2,}/);
    if (parts.length < 5) return null;
    try {
        const cubagem = formatNumber(parts[parts.length - 1]);
        const peso = formatNumber(parts[parts.length - 2]);
        const qtEmb = formatNumber(parts[parts.length - 3]);
        const qtAloc = formatNumber(parts[parts.length - 4]);
        const unid = parts[parts.length - 5];
        const desc = parts.slice(1, parts.length - 5).join(' ');
        return {
            "Embarque": ctx.embarque, "Cliente": ctx.cliente, "Pedido": ctx.pedido,
            "Ped. Cliente": ctx.pedCliente, "Dep": ctx.dep, "Emit": ctx.emit,
            "Tipo": ctx.tipo, "Representante": ctx.rep, "Previsão": ctx.previsao,
            "Data Pedido": ctx.dtPedido, "Item": parts[0], "Descrição": desc,
            "Unidade": unid, "Qt Alocada": qtAloc, "Qt Embalagem": qtEmb,
            "Peso Total": peso, "Cubagem": cubagem
        };
    } catch (e) { return null; }
}

function renderTable() {
    const data = getFilteredData();
    tableHead.innerHTML = `<tr>${columns.map(c => `<th>${c}</th>`).join('')}</tr>`;
    tableBody.innerHTML = data.slice(0, 100).map(row =>
        `<tr>${columns.map(c => `<td>${row[c] || ''}</td>`).join('')}</tr>`
    ).join('');

    const totals = calculateTotals(data);
    statsEl.innerHTML = `
        <div class="stats-summary">
            <div class="stat-card"><span class="label">Registros</span><span class="value">${data.length}</span></div>
            <div class="stat-card"><span class="label">Total Embalagens</span><span class="value">${totals.embalagem.toFixed(2)}</span></div>
            <div class="stat-card"><span class="label">Peso Total (kg)</span><span class="value">${totals.peso.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</span></div>
            <div class="stat-card"><span class="label">Cubagem (m³)</span><span class="value">${totals.cubagem.toFixed(4)}</span></div>
            <div class="stat-card error-card ${failedLinesLog.length > 0 ? 'has-errors' : ''}" onclick="openErrorModal()">
                <span class="label">Erros de Linha</span><span class="value">${failedLinesLog.length}</span>
            </div>
        </div>
    `;
    resultsSection.classList.remove('hidden');
}

function calculateTotals(data) {
    return data.reduce((acc, row) => {
        acc.embalagem += parseFloat(row["Qt Embalagem"] || 0);
        acc.peso += parseFloat(row["Peso Total"] || 0);
        acc.cubagem += parseFloat(row["Cubagem"] || 0);
        return acc;
    }, { embalagem: 0, peso: 0, cubagem: 0 });
}

function generatePrintReport() {
    const data = getFilteredData();
    if (data.length === 0) return;

    // Agrupar por Pedido
    const grouped = {};
    data.forEach(item => {
        if (!grouped[item.Pedido]) grouped[item.Pedido] = { items: [], totals: { emb: 0, peso: 0, cub: 0 }, clin: item.Cliente, emb: item.Embarque };
        grouped[item.Pedido].items.push(item);
        grouped[item.Pedido].totals.emb += parseFloat(item["Qt Embalagem"] || 0);
        grouped[item.Pedido].totals.peso += parseFloat(item["Peso Total"] || 0);
        grouped[item.Pedido].totals.cub += parseFloat(item["Cubagem"] || 0);
    });

    let html = `
        <div class="print-header">
            <h1>Analisador de Embarques .txt (Datasul)</h1>
            <p style="color: #64748b; font-size: 0.9rem;">Relatório Consolidado de Pedidos | Gerado em: ${new Date().toLocaleString('pt-BR')}</p>
        </div>
        <table class="print-table">
            <thead>
                <tr>
                    <th>Embarque</th>
                    <th>Pedido</th>
                    <th>Cliente</th>
                    <th style="text-align:right">Embalagens</th>
                    <th style="text-align:right">Peso (kg)</th>
                    <th style="text-align:right">Cubagem (m³)</th>
                </tr>
            </thead>
            <tbody>
    `;

    let gTotal = { emb: 0, peso: 0, cub: 0 };
    const sortedPedidos = Object.keys(grouped).sort();

    sortedPedidos.forEach(pedidoNum => {
        const group = grouped[pedidoNum];
        html += `
            <tr>
                <td>${group.emb}</td>
                <td>${pedidoNum}</td>
                <td>${group.clin}</td>
                <td style="text-align:right">${group.totals.emb.toFixed(2)}</td>
                <td style="text-align:right">${group.totals.peso.toFixed(2)}</td>
                <td style="text-align:right">${group.totals.cub.toFixed(4)}</td>
            </tr>
        `;

        gTotal.emb += group.totals.emb;
        gTotal.peso += group.totals.peso;
        gTotal.cub += group.totals.cub;
    });

    html += `
            <tr class="grand-total-row">
                <td colspan="3" style="text-align:right">TOTAIS GERAIS:</td>
                <td style="text-align:right">${gTotal.emb.toFixed(2)}</td>
                <td style="text-align:right">${gTotal.peso.toFixed(2)}</td>
                <td style="text-align:right">${gTotal.cub.toFixed(4)}</td>
            </tr>
        </tbody>
    </table>
    `;

    printArea.innerHTML = html;
    window.print();
}

function exportData(format) {
    const dataToExport = getFilteredData();
    if (dataToExport.length === 0) return;
    const wsData = [columns, ...dataToExport.map(item => columns.map(col => item[col] || ''))];
    const totals = calculateTotals(dataToExport);
    wsData.push(columns.map(col => {
        if (col === "Qt Embalagem") return totals.embalagem.toFixed(2);
        if (col === "Peso Total") return totals.peso.toFixed(2);
        if (col === "Cubagem") return totals.cubagem.toFixed(4);
        if (col === "Descrição") return "TOTAIS GERAIS:";
        return "";
    }));
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "ItemReport");
    XLSX.writeFile(wb, `Analisador_de_Embarques_Datasul.${format}`);
}

function formatNumber(str) {
    if (!str) return 0;
    let val = str.replace(/_/g, '').trim();
    if (val === '') return 0;
    let cleaned = val.replace(/[^\d\.,-]/g, '').replace(/\./g, '').replace(',', '.');
    return parseFloat(cleaned) || 0;
}

function setupEmbarqueFilter() {
    embarqueFilter.innerHTML = '<option value="all">Todos os Embarques</option>' +
        Array.from(allEmbarques).sort().map(emb => `<option value="${emb}">Embarque ${emb}</option>`).join('');
}

function getFilteredData() {
    return currentFilter === 'all' ? parsedData : parsedData.filter(item => item.Embarque === currentFilter);
}

function showError(msg) { statusMessage.textContent = msg; statusMessage.style.color = '#e11d48'; }
function showStatus(msg) { statusMessage.textContent = msg; statusMessage.style.color = '#6b7280'; }
