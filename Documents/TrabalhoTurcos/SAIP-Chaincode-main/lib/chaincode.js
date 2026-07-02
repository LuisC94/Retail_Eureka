/*
 * Copyright IBM Corp. All Rights Reserved.
 *
 * SPDX-License-Identifier: Apache-2.0
 */

'use strict';

// Deterministic JSON.stringify()
const stringify = require('json-stringify-deterministic');
const sortKeysRecursive = require('sort-keys-recursive');
const { Contract } = require('fabric-contract-api');

class Chaincode extends Contract {

    async InitLedger(ctx) {

    }

    // CreateoRDER issues a new ORDER to the world state with given details.
    async CreateOrder(ctx, orderJSON) {
        console.log("CreateOrder: Received JSON:", orderJSON);
        const order = JSON.parse(orderJSON);

        const exists = await this.OrderExists(ctx, order.id);
        if (exists) {
            throw new Error(`The order ${order.id} already exists`);
        }

        await ctx.stub.putState(order.id, Buffer.from(JSON.stringify(order)));
        return JSON.stringify(order);
    }

    // ReadOrder returns the order stored in the world state with given id.
    async ReadOrder(ctx, id) {
        const orderAsBytes = await ctx.stub.getState(id);
        if (!orderAsBytes || orderAsBytes.length === 0) {
            throw new Error(`Order ${id} does not exist`);
        }
        return orderAsBytes.toString();
    }

    // UpdateOrder updates an existing order with new JSON data.
    async UpdateOrder(ctx, id, orderJSON) {
        const order = JSON.parse(orderJSON);

        const exists = await this.OrderExists(ctx, id);
        if (!exists) {
            throw new Error(`The order ${id} does not exist`);
        }

        // Ensure ID integrity
        if (order.id !== id) {
            throw new Error(`Order ID mismatch: ${id} vs ${order.id}`);
        }

        await ctx.stub.putState(id, Buffer.from(JSON.stringify(order)));
        return JSON.stringify(order);
    }

    // UpdateOrderStatus updates an existing order status in the world state with provided parameters.
    async UpdateOrderStatus(ctx, id, orderStatus, orderProductId, status, proccessDate) {
        const orderAsBytes = await ctx.stub.getState(id);
        if (!orderAsBytes || orderAsBytes.length === 0) {
            throw new Error(`Order ${id} does not exist`);
        }

        const order = JSON.parse(orderAsBytes.toString());
        order.orderStatus = orderStatus;

        order.orderProducts.forEach(orderProduct => {
            if (orderProduct.id == orderProductId) {
                orderProduct.status = status;
                orderProduct.proccessDate = proccessDate;
            }
        });

        await ctx.stub.putState(id, Buffer.from(JSON.stringify(order)));
    }

    // OrderExists returns true when order with given ID exists in world state.
    async OrderExists(ctx, id) {
        const orderJSON = await ctx.stub.getState(id);
        return orderJSON && orderJSON.length > 0;
    }

    // GetAllOrders returns all orders found in the world state.
    async GetAllOrders(ctx) {
        const allResults = [];
        // range query with empty string for startKey and endKey does an open-ended query of all assets in the chaincode namespace.
        const iterator = await ctx.stub.getStateByRange('', '');
        let result = await iterator.next();
        while (!result.done) {
            const strValue = Buffer.from(result.value.value.toString()).toString('utf8');
            let record;
            try {
                record = JSON.parse(strValue);
            } catch (err) {
                console.log(err);
                record = strValue;
            }
            allResults.push(record);
            result = await iterator.next();
        }
        return JSON.stringify(allResults);
    }

    // GetHistoryForAsset returns the history of key values across time.
    async GetHistoryForAsset(ctx, id) {
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
