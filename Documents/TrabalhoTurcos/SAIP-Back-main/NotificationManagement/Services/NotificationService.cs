using Microsoft.EntityFrameworkCore;
using NotificationManagement.DbContexts;
using NotificationManagement.Entity;
using NotificationManagement.Interfaces;
using NotificationManagement.Model;
using System.Data;

namespace NotificationManagement.Services
{
    public class NotificationService : INotificationService
    {
        private readonly NotificationManagementContext _dbContext;
        public NotificationService(NotificationManagementContext dbContext)
        {
            _dbContext = dbContext;
        }
        public async Task<Result<List<Notification>>> GetNotifications(long userId)
        {
            var result = new Result<List<Notification>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Notifications.Where(x => !x.IsDeleted && x.UserId == userId).OrderByDescending(o => o.Date).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }
        public async Task<Result<Notification>> Save(Notification notification)
        {
            var result = new Result<Notification>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.Notifications.Where(x => (x.Id == notification.Id) && !x.IsDeleted).Any())
                    {
                        notification.Date = DateTime.UtcNow;
                        _dbContext.Add(notification);
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(notification);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı Id ile tanımlı bir bildirim bulunmaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }
        public async Task<Result<Notification>> Delete(long id)
        {
            var result = new Result<Notification>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldNotification = await _dbContext.Notifications.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldNotification != null)
                    {
                        oldNotification.IsDeleted = true;
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldNotification);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }
        public async Task<Result<Notification>> Read(long id)
        {
            var result = new Result<Notification>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var Notification = await _dbContext.Notifications.Where(x => x.Id == id && !x.IsDeleted && !x.IsReaded).FirstOrDefaultAsync();
                    if (Notification != null)
                    {
                        Notification.IsReaded = true;
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(Notification);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();
                }
            }

            return result;
        }
    }
}




