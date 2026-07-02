export class UserModel {
    id: number;
    name: string;
    surname: string;
    nameSurname: string;
    phone: string;
    email: string;
    password?: string;
    username: string;
    isDeleted: boolean;
    isSystemData: boolean;
    organizations: number[];
    roles: number[];
    isProducer: boolean;
    fileId?: number;
    fileResult?: any;
}