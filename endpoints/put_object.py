from .base import Base


class PutObject(Base):

    def check_permissions(self):
        """
        Placeholder... dunno if we'll even need/use it

        :return: N/A
        """
        pass

    def get_object(self, pk):
        """
        Get a Django model instance to save

        :param pk: Primary key <integer>
        :return: Instance of model set
        """
        self.object = self.model_path.objects.get(pk=pk)
