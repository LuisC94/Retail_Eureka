import { ProductModel } from "./product.model";

export class BasketModel {
    id: number;
    userId: number;
    productId?: number;
    product?: ProductModel;
    isDeleted: boolean;
    numberOf?: number;
    totalPrice?: number;
    fileResult?: any;
}
  