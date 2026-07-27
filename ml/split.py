def chronological_split(df, train_ratio=.7, val_ratio=.15):
    df=df.sort_values('Date').reset_index(drop=True); n=len(df); a=int(n*train_ratio); b=int(n*(train_ratio+val_ratio))
    if a<50 or b<=a or n-b<20: raise ValueError(f'データ不足です。特徴量生成後 {n} 試合。より多くのCSVを追加してください。')
    return df.iloc[:a].copy(),df.iloc[a:b].copy(),df.iloc[b:].copy()
