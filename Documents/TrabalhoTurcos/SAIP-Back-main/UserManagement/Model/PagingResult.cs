namespace UserManagement.Model
{
    public class PagingResult<T>
    {
        public T Items { get; set; }

        public int TotalCount { get; set; }
    }
}
