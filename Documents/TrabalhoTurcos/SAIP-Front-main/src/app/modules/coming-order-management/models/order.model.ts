import { BasketModel } from "../../basket-management/models/basket.model";
import { UserAddressModel } from "../../user-management/models/user-address.model";
import { OrderProductModel } from "./orderproduct.model";

export class OrderModel {
    id: number;
    basketId: number;
    basket?: BasketModel;
    userId: number;
    price: number;
    priceStr?: string;
    orderDate?: string;
    orderNo?: string;
    orderStatus?: number;
    orderStatusStr?: string;
    orderProducts?: OrderProductModel[];
    deliveryAddressId?: number;
    deliveryAddress?: UserAddressModel;
    invoiceAddressId?: number;
    invoiceAddress?: UserAddressModel;
  }
  