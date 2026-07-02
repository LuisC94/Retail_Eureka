using NotificationManagement.Entity;
using NotificationManagement.Model;

namespace NotificationManagement.Interfaces
{
    public interface INotificationService
    {
        Task<Result<List<Notification>>> GetNotifications(long userId);
        Task<Result<Notification>> Save(Notification notification);
        Task<Result<Notification>> Delete(long id);
        Task<Result<Notification>> Read(long id);
    }
}
