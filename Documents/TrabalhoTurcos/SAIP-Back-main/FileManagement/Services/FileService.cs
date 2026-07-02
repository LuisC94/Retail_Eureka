using Microsoft.EntityFrameworkCore;
using FileManagement.DbContexts;
using FileManagement.Interfaces;
using FileManagement.Model;
using System.Data;

namespace FileManagement.Services
{
    public class FileService : IFileService
    {
        private readonly FileManagementContext _dbContext;

        public FileService(FileManagementContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Result<Entity.File>> Delete(long id)
        {
            var result = new Result<Entity.File>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var file = await _dbContext.Files.Where(x => x.Id == id).FirstOrDefaultAsync();

                    if(file != null)
                    {
                        file.IsDeleted = true;
                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(file);
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

        public async Task<Result<Entity.File>> GetById(long id)
        {
            var result = new Result<Entity.File>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var file = await _dbContext.Files.Where(x => x.Id == id).FirstOrDefaultAsync();

                    result.SetData(file);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
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

        public async Task<Result<Entity.File>> Save(IFormFile file)
        {
            var result = new Result<Entity.File>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var filePath = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", Guid.NewGuid().ToString() + Path.GetExtension(file.FileName));

                    Entity.File dbItem = new Entity.File();
                    dbItem.Name = file.FileName;
                    dbItem.Length = file.Length;
                    dbItem.Path = filePath;
                    dbItem.Extension = Path.GetExtension(file.FileName);
                    dbItem.ContentType = file.ContentType;
                    dbItem.IsDeleted = false;

                    _dbContext.Add(dbItem);

                    await _dbContext.SaveChangesAsync();
                    transaction.Commit();

                    using (var stream = System.IO.File.Create(filePath))
                    {
                        await file.CopyToAsync(stream);
                    }

                    result.SetData(dbItem);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
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
    }
}
