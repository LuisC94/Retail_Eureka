/*
 * Copyright Retail Eureka & Hyperledger Fabric
 * Smart Contract 'saip': Rastreabilidade Física Pública com Sigilo Comercial Bilateral
 *
 * SPDX-License-Identifier: Apache-2.0
 */

'use strict';

const { Contract } = require('fabric-contract-api');
const stringify = require('json-stringify-deterministic');
const sortKeysRecursive = require('sort-keys-recursive');

/**
 * Obtém o carimbo temporal determinístico oficial da transação (igual em todos os peers).
 */
function getTxTimestampIso(ctx, fallbackDate) {
    if (fallbackDate) return fallbackDate;
    try {
        const txTimestamp = ctx.stub.getTxTimestamp();
        if (txTimestamp && txTimestamp.seconds) {
            const seconds = typeof txTimestamp.seconds.low !== 'undefined' ? txTimestamp.seconds.low : Number(txTimestamp.seconds);
            return new Date(seconds * 1000).toISOString();
        }
    } catch (e) {
        console.error("Erro ao obter getTxTimestamp:", e);
    }
    return fallbackDate || '1970-01-01T00:00:00.000Z';
}

/**
 * Função auxiliar para aplicar o filtro de privacidade e sigilo bilateral.
 */
function filterOrderPrivacy(order, callerId) {
    if (!order) return order;

    try {
        const filtered = JSON.parse(JSON.stringify(order));
        const caller = (callerId || '').toString().trim();

        // 1. Filtrar Transações Comerciais (commercial_deals)
        if (Array.isArray(filtered.commercial_deals)) {
            if (caller === 'Admin' || caller === 'Auditor') {
                // Administradores e Auditores têm acesso a auditoria fiscal completa
            } else if (caller) {
                // O interveniente apenas vê as transações onde foi Vendedor ou Comprador
                filtered.commercial_deals = filtered.commercial_deals.filter(deal => 
                    deal && (deal.sellerId === caller || deal.buyerId === caller)
                );
            } else {
                // Consulta anónima ou pública (ex: consumidor final): zero dados financeiros
                filtered.commercial_deals = [];
            }
        }

        // 2. Garantir que dados financeiros isolados na raiz não vazam
        if (filtered.financial_details) {
            delete filtered.financial_details;
        }

        // 3. Filtrar envelope de dados privados genéricos (private_data) se existir
        if (filtered.private_data) {
            const isAuthorized = caller && (
                caller === 'Admin' || 
                caller === 'Auditor' ||
                caller === filtered.producerName ||
                caller === filtered.buyerName ||
                (Array.isArray(filtered.authorized_parties) && filtered.authorized_parties.includes(caller))
            );

            if (!isAuthorized) {
                filtered.private_data = {};
            }
        }

        return filtered;
    } catch (e) {
        console.error("Erro no filterOrderPrivacy:", e);
        return order;
    }
}

/**
 * Campos que só podem crescer (nunca ser apagados ou reescritos) por uma atualização.
 * Protege contra quem grava de volta um estado já filtrado pelo sigilo (sem os negócios de terceiros).
 */
const PROTECTED_KEYS = ['id', 'commercial_deals', 'custody_chain', 'private_data', 'financial_details'];

function mergeProtectedFields(stored, incoming) {
    const merged = Object.assign({}, incoming);

    // 1. Negócios comerciais: mantêm-se todos os gravados; só se acrescentam dealIds novos
    const storedDeals = Array.isArray(stored.commercial_deals) ? stored.commercial_deals : [];
    const knownIds = new Set(storedDeals.map(d => d && d.dealId).filter(Boolean));
    const newDeals = (Array.isArray(incoming.commercial_deals) ? incoming.commercial_deals : [])
        .filter(d => d && d.dealId && !knownIds.has(d.dealId));
    merged.commercial_deals = storedDeals.concat(newDeals);

    // 2. Cadeia de custódia: append-only (só se aceitam entradas além das já gravadas)
    const storedChain = Array.isArray(stored.custody_chain) ? stored.custody_chain : [];
    const incomingChain = Array.isArray(incoming.custody_chain) ? incoming.custody_chain : [];
    merged.custody_chain = storedChain.concat(incomingChain.slice(storedChain.length));

    // 3. Dados privados: um envelope vazio (filtrado) nunca apaga o gravado
    const storedPrivate = (stored.private_data && typeof stored.private_data === 'object') ? stored.private_data : {};
    const incomingPrivate = (incoming.private_data && typeof incoming.private_data === 'object') ? incoming.private_data : {};
    merged.private_data = Object.assign({}, storedPrivate, incomingPrivate);
    if (Object.keys(merged.private_data).length === 0 && !('private_data' in stored)) {
        delete merged.private_data;
    }

    // 4. Dados financeiros nunca ficam na raiz
    delete merged.financial_details;
    merged.id = stored.id;
    return merged;
}

class Chaincode extends Contract {

    async InitLedger(ctx) {
        console.log("InitLedger: Smart Contract SAIP inicializado com sucesso.");
    }

    /**
     * CreateOrder: Regista um novo lote na Blockchain de forma 100% determinística.
     */
    async CreateOrder(ctx, orderJSON, callerId) {
        console.log("CreateOrder: Received JSON:", orderJSON);
        let order;
        try {
            order = typeof orderJSON === 'string' ? JSON.parse(orderJSON) : orderJSON;
        } catch (e) {
            throw new Error(`JSON parse error in CreateOrder: ${e.message}`);
        }

        if (!order || !order.id) {
            throw new Error("O lote deve conter um campo 'id' válido.");
        }

        const exists = await this.OrderExists(ctx, order.id);
        if (exists) {
            throw new Error(`The order ${order.id} already exists`);
        }

        const timestamp = getTxTimestampIso(ctx, order.harvestDate);

        // Inicializar cadeia de custódia física se não fornecida
        if (!Array.isArray(order.custody_chain)) {
            order.custody_chain = [];
            order.custody_chain.push({
                timestamp: timestamp,
                actorId: order.producerName || callerId || 'PRODUCER',
                action: 'HARVEST',
                details: order.plantation_info || { description: 'Colheita Inicial do Lote' }
            });
        }

        // Inicializar lista de transações comerciais se não fornecida
        if (!Array.isArray(order.commercial_deals)) {
            order.commercial_deals = [];
            if (order.financial_details || (order.pricePerKg && order.buyerName)) {
                order.commercial_deals.push({
                    dealId: `DEAL-${order.id}-1`,
                    sellerId: order.producerName || callerId || 'PRODUCER',
                    buyerId: order.buyerName || 'DISTRIBUTOR',
                    financial_details: order.financial_details || {
                        pricePerKg: order.pricePerKg,
                        totalAmount: order.totalAmount
                    },
                    timestamp: timestamp
                });
            }
        }

        // Remover financial_details da raiz para segurança
        delete order.financial_details;

        // Estado atual padrão
        if (!order.orderStatus && !order.currentStatus) {
            order.orderStatus = 'HARVESTED';
            order.currentStatus = 'HARVESTED';
        }

        // Escrita determinística no Ledger
        await ctx.stub.putState(order.id, Buffer.from(stringify(sortKeysRecursive(order))));
        return stringify(sortKeysRecursive(filterOrderPrivacy(order, callerId)));
    }

    /**
     * TransferCustody: Regista uma nova etapa de movimentação física na cadeia de custódia.
     */
    async TransferCustody(ctx, id, actorId, action, detailsJSON, callerId) {
        const orderAsBytes = await ctx.stub.getState(id);
        if (!orderAsBytes || orderAsBytes.length === 0) {
            throw new Error(`Order ${id} does not exist`);
        }

        const order = JSON.parse(orderAsBytes.toString());
        let details = {};
        try {
            details = detailsJSON ? (typeof detailsJSON === 'string' ? JSON.parse(detailsJSON) : detailsJSON) : {};
        } catch (e) {
            details = { description: detailsJSON };
        }

        if (!Array.isArray(order.custody_chain)) {
            order.custody_chain = [];
        }

        const event = {
            timestamp: getTxTimestampIso(ctx),
            actorId: actorId || callerId || 'UNKNOWN_ACTOR',
            action: action,
            details: details
        };

        order.custody_chain.push(event);
        order.orderStatus = action;
        order.currentStatus = action;

        await ctx.stub.putState(id, Buffer.from(stringify(sortKeysRecursive(order))));
        return stringify(sortKeysRecursive(filterOrderPrivacy(order, callerId)));
    }

    /**
     * RecordCommercialDeal: Regista uma nova venda/revenda entre duas empresas para o lote.
     */
    async RecordCommercialDeal(ctx, id, dealJSON, callerId) {
        const orderAsBytes = await ctx.stub.getState(id);
        if (!orderAsBytes || orderAsBytes.length === 0) {
            throw new Error(`Order ${id} does not exist`);
        }

        const order = JSON.parse(orderAsBytes.toString());
        let deal;
        try {
            deal = typeof dealJSON === 'string' ? JSON.parse(dealJSON) : dealJSON;
        } catch (e) {
            throw new Error(`JSON parse error in RecordCommercialDeal: ${e.message}`);
        }

        if (!deal || !deal.sellerId || !deal.buyerId) {
            throw new Error("O registo comercial exige sellerId e buyerId definidos.");
        }

        if (!Array.isArray(order.commercial_deals)) {
            order.commercial_deals = [];
        }

        deal.dealId = deal.dealId || `DEAL-${id}-${order.commercial_deals.length + 1}`;
        deal.timestamp = deal.timestamp || getTxTimestampIso(ctx);

        order.commercial_deals.push(deal);

        await ctx.stub.putState(id, Buffer.from(stringify(sortKeysRecursive(order))));
        return stringify(sortKeysRecursive(filterOrderPrivacy(order, callerId)));
    }

    /**
     * ReadOrder: Lê um lote aplicando o filtro de sigilo bilateral conforme o callerId.
     */
    async ReadOrder(ctx, id, callerId) {
        const orderAsBytes = await ctx.stub.getState(id);
        if (!orderAsBytes || orderAsBytes.length === 0) {
            throw new Error(`Order ${id} does not exist`);
        }

        const order = JSON.parse(orderAsBytes.toString());
        const filtered = filterOrderPrivacy(order, callerId);
        return stringify(sortKeysRecursive(filtered));
    }

    /**
     * UpdateOrder: Atualiza um lote existente de forma determinística.
     * Os negócios comerciais, a cadeia de custódia e os dados privados já gravados são preservados
     * (ver mergeProtectedFields), mesmo que o estado enviado tenha sido lido com filtro de sigilo.
     */
    async UpdateOrder(ctx, id, orderJSON, callerId) {
        const order = typeof orderJSON === 'string' ? JSON.parse(orderJSON) : orderJSON;

        const storedBytes = await ctx.stub.getState(id);
        if (!storedBytes || storedBytes.length === 0) {
            throw new Error(`The order ${id} does not exist`);
        }

        if (order.id !== id) {
            throw new Error(`Order ID mismatch: ${id} vs ${order.id}`);
        }

        const stored = JSON.parse(storedBytes.toString());
        const merged = mergeProtectedFields(stored, order);

        await ctx.stub.putState(id, Buffer.from(stringify(sortKeysRecursive(merged))));
        return stringify(sortKeysRecursive(filterOrderPrivacy(merged, callerId)));
    }

    /**
     * UpdateOrderStatus: Altera o estado de um lote e acrescenta campos adicionais,
     * partindo do estado COMPLETO gravado no ledger (sem passar pelo filtro de sigilo).
     * Os campos protegidos (negócios, custódia, dados privados) não podem ser alterados por aqui.
     */
    async UpdateOrderStatus(ctx, id, newStatus, additionalJSON, callerId) {
        const storedBytes = await ctx.stub.getState(id);
        if (!storedBytes || storedBytes.length === 0) {
            throw new Error(`The order ${id} does not exist`);
        }
        if (!newStatus) {
            throw new Error("UpdateOrderStatus exige um novo estado.");
        }

        let additional = {};
        if (additionalJSON) {
            try {
                additional = typeof additionalJSON === 'string' ? JSON.parse(additionalJSON) : additionalJSON;
            } catch (e) {
                throw new Error(`JSON parse error in UpdateOrderStatus: ${e.message}`);
            }
        }

        const order = JSON.parse(storedBytes.toString());
        if (additional && typeof additional === 'object' && !Array.isArray(additional)) {
            Object.keys(additional).forEach(key => {
                if (!PROTECTED_KEYS.includes(key)) {
                    order[key] = additional[key];
                }
            });
        }
        order.orderStatus = newStatus;
        order.currentStatus = newStatus;

        await ctx.stub.putState(id, Buffer.from(stringify(sortKeysRecursive(order))));
        return stringify(sortKeysRecursive(filterOrderPrivacy(order, callerId)));
    }

    /**
     * OrderExists: Verifica se o lote existe.
     */
    async OrderExists(ctx, id) {
        const orderJSON = await ctx.stub.getState(id);
        return orderJSON && orderJSON.length > 0;
    }

    /**
     * GetAllOrders: Retorna todos os lotes aplicando a filtragem de sigilo a cada um.
     */
    async GetAllOrders(ctx, callerId) {
        const allResults = [];
        const iterator = await ctx.stub.getStateByRange('', '');
        let result = await iterator.next();
        while (!result.done) {
            const strValue = Buffer.from(result.value.value.toString()).toString('utf8');
            try {
                const record = JSON.parse(strValue);
                allResults.push(filterOrderPrivacy(record, callerId));
            } catch (err) {
                console.log(err);
            }
            result = await iterator.next();
        }
        return stringify(sortKeysRecursive(allResults));
    }

    /**
     * GetOrderHistory: Retorna o histórico de transações do Ledger.
     * Cada versão do lote passa pelo mesmo filtro de sigilo do ReadOrder, conforme o callerId
     * (sem callerId = consulta pública, sem dados comerciais).
     */
    async GetOrderHistory(ctx, id, callerId) {
        const historyIterator = await ctx.stub.getHistoryForKey(id);
        const results = [];
        let res = await historyIterator.next();
        while (!res.done) {
            if (res.value) {
                let value = '';
                try {
                    const raw = res.value.value.toString('utf8');
                    value = raw ? stringify(sortKeysRecursive(filterOrderPrivacy(JSON.parse(raw), callerId))) : '';
                } catch (e) {
                    // Valor ilegível: não devolver conteúdo em bruto (poderia expor dados comerciais)
                    value = '';
                }
                const obj = {
                    txId: res.value.txId,
                    timestamp: res.value.timestamp,
                    isDelete: res.value.is_delete,
                    value: value
                };
                results.push(obj);
            }
            res = await historyIterator.next();
        }
        await historyIterator.close();
        return JSON.stringify(results);
    }
}

module.exports = Chaincode;
