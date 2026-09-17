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
     */
    async UpdateOrder(ctx, id, orderJSON, callerId) {
        const order = typeof orderJSON === 'string' ? JSON.parse(orderJSON) : orderJSON;

        const exists = await this.OrderExists(ctx, id);
        if (!exists) {
            throw new Error(`The order ${id} does not exist`);
        }

        if (order.id !== id) {
            throw new Error(`Order ID mismatch: ${id} vs ${order.id}`);
        }

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
     */
    async GetOrderHistory(ctx, id) {
        const historyIterator = await ctx.stub.getHistoryForKey(id);
        const results = [];
        let res = await historyIterator.next();
        while (!res.done) {
            if (res.value) {
                const obj = {
                    txId: res.value.txId,
                    timestamp: res.value.timestamp,
                    isDelete: res.value.is_delete,
                    value: res.value.value.toString('utf8')
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
