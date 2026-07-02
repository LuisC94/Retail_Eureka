import { CategoryModel } from "./category.model";
import { ProductCommentModel } from "./comment.model";

export class ProductModel {
    id: number;
    name: string;
    price: number;
    priceStr?: string;
    fileId: number;
    fileResult: any;
    userId: number;
    isDeleted: boolean;
    brand?: string;
    description?: string;
    stock: number;
    rating?: number;
    sale?: number;
    discountedPrice?: number;
    categoryId: number;
    category?: CategoryModel;
    starsStatus?: string[];
    isMostRating: boolean;
    comments?: ProductCommentModel[];
    commentsCount: number;
  }
  