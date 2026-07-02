export interface NotificationModel {
    id: number;
    userId: number;
    message: string;
    isReaded: boolean;
    isDeleted: boolean;
    date: string;
    time: string;
    state: string;
    link: string;
}