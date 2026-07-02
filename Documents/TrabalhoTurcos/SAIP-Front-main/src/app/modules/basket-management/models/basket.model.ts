import { ProductModel } from "../../shopping/models/product.model";

export class BasketModel {
    id: number;
    productId?: number;
    product?: ProductModel;
    userId: number;
    isDeleted: boolean;
    numberOf?: number;
    totalPrice?: number;
    fileResult?: any;
  }
  