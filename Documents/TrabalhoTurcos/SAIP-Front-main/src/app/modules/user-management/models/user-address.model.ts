import { UserModel } from "./user.model";

export class UserAddressModel {
    id: number;
    userId: number;
    user?: UserModel;
    name: string;
    surname: string;
    phone: string;
    isDeleted: boolean;
    address: string;
    country: string;
    city: string;
    district: string;
    addressHeader: string;
    invoiceType: number;
    vkn?: string;
    vergiDairesi?: string;
    firmaAdi?: string;
    selected?: boolean;
}