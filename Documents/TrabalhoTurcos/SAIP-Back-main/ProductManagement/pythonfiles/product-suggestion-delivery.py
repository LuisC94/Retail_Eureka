import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from scipy.sparse import csr_matrix

# Now, we create user-item matrix using scipy csr matrix
def create_matrix(df):
     
    N = len(df['userId'].unique())
    M = len(df['productId'].unique())

    # Map Ids to indices
    user_mapper = dict(zip(np.unique(df["userId"]), list(range(N))))
    product_mapper = dict(zip(np.unique(df["productId"]), list(range(M))))
     
    # Map indices to IDs
    user_inv_mapper = dict(zip(list(range(N)), np.unique(df["userId"])))
    product_inv_mapper = dict(zip(list(range(M)), np.unique(df["productId"])))
     
    user_index = [user_mapper[i] for i in df['userId']]
    product_index = [product_mapper[i] for i in df['productId']]
 
    X = csr_matrix((df["rating"], (product_index, user_index)), shape=(M, N))
    return X, user_mapper, product_mapper, user_inv_mapper, product_inv_mapper
     
#Find similar products using KNN
def find_similar_products(product_mapper, product_inv_mapper, product_id, X, k, metric='cosine', show_distance=False):
     
    neighbour_ids = []
     
    product_ind = product_mapper[product_id]
    produt_vec = X[product_ind]
    k+=1
    kNN = NearestNeighbors(n_neighbors=k, algorithm="brute", metric=metric)
    kNN.fit(X)
    produt_vec = produt_vec.reshape(1,-1)
    neighbour = kNN.kneighbors(produt_vec, return_distance=show_distance)
    for i in range(0,k):
        n = neighbour.item(i)
        neighbour_ids.append(product_inv_mapper[n])
    neighbour_ids.pop(0)
    return neighbour_ids

def recommend_products_for_user(ratings, products, user_id, X, user_mapper, user_inv_mapper, product_mapper, product_inv_mapper):
    df1 = ratings[ratings['userId'] == user_id]
     
    if df1.empty:
        print(f"User with ID {user_id} does not exist.")
        return
 
    product_id = df1[df1['rating'] == max(df1['rating'])]['productId'].iloc[0]
 
    product_names = dict(zip(products['productId'], products['name']))
    
    k = len(ratings['productId'].unique())
    if k < 10:
        k = k-1
    else:
        k = 10

    similar_ids = find_similar_products(product_mapper, product_inv_mapper, product_id, X, k)
    product_name = product_names.get(product_id, "Product not found")
 
    if product_name == "Product not found":
        print(f"Product with ID {product_id} not found.")
        return
 
    return similar_ids

def run(user_id):
    ratings = pd.read_csv("http://localhost:5055/api/Product/GetDeliveryRatingsCSVFormat")
    products = pd.read_csv("http://localhost:5055/api/Product/GetProductsCSVFormat")

    X, user_mapper, product_mapper, user_inv_mapper, product_inv_mapper = create_matrix(ratings)
    ids = recommend_products_for_user(ratings, products, user_id, X, user_mapper, user_inv_mapper, product_mapper, product_inv_mapper)
    ids = [arr.tolist() for arr in ids]
    print(ids)
    return ids