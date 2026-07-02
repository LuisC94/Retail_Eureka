using FileManagement.Model;

namespace FileManagement.Interfaces
{
    public interface IFileService
    {
        Task<Result<Entity.File>> Save(IFormFile file);
        Task<Result<Entity.File>> Delete(long id);

        Task<Result<Entity.File>> GetById(long id);
    }
}
