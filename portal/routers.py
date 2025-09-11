# routers.py
class P12Router:
    """
    Um roteador para controlar todas as operações de banco de dados nos modelos
    do ERP Protheus (P12).
    """
    
    # Adicionado 'SBM010' à lista
    erp_tables = ['SA2010', 'SC7010', 'SC8010', 'SYS_COMPANY', 'SC1010', 'SE4010', 'SD1010', 'SBM010', 'SCR010', 'SYS_USR']

    def db_for_read(self, model, **hints):
        """
        Lê os modelos do ERP do banco p12_bi e o restante do banco default.
        """
        if model._meta.db_table in self.erp_tables:
            return 'p12_bi'
        return 'default'

    def db_for_write(self, model, **hints):
        """
        Escreve apenas no banco 'default'. Bloqueia a escrita no ERP.
        """
        if model._meta.db_table in self.erp_tables:
            return None  # Impede a escrita no banco do ERP
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """
        Permite relações se ambos os objetos forem do banco 'default' (logistica).
        """
        if obj1._meta.managed and obj2._meta.managed:
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Garante que os modelos do ERP não sejam migrados e que os modelos da app
        sejam migrados apenas para o banco 'default'.
        """
        if db == 'p12_bi':
            return False
        # Adicionado 'sbm' à lista de modelos não gerenciados
        return app_label == 'portal' and model_name not in ['sa2fornecedor', 'sc7pedidoitem', 'sc8cotacaoitem', 'sc1', 'se4', 'syscompany', 'sd1nfitem', 'sbm']
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'p12_bi':
            return False
        # Adicionado 'scr010aprovacao' e 'sysusr' à lista de modelos não gerenciados
        return app_label == 'portal' and model_name not in [
            'sa2fornecedor', 'sc7pedidoitem', 'sc8cotacaoitem', 'sc1', 'se4', 
            'syscompany', 'sd1nfitem', 'sbm', 'scr010aprovacao', 'sysusr'
        ]