from rosbagdatabricks.RosMessageParserVisitor import RosMessageParserVisitor
from rosbagdatabricks.RosMessageParser import RosMessageParser
from pyspark.sql.types import StructType, StringType

import re

class RosMessageSchemaVisitor(RosMessageParserVisitor):

    def visitRosbag_input(self, ctx):
        ros_message = ctx.getChild(0)
        struct_names = self.visitFieldDeclarationChildren(ros_message)
        
        struct = self.visitNestedMessageChildren(ctx, struct_names)
        return struct

    def visitFieldDeclarationChildren(self, node):
        result = {}
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return result
    
            c = node.getChild(i)
            if isinstance(c, RosMessageParser.Field_declarationContext):
                childResult = c.accept(self)
                result = self.aggregateStructNames(result, childResult)
    
        return result

    def visitField_declaration(self, node):
        return {node.getChild(0).getText(): node.getChild(1).getText()}

    def aggregateStructNames(self, aggregate, nextResult):
        aggregate.update(nextResult)
        return aggregate

    def visitNestedMessageChildren(self, node, struct_name):
        result = StructType()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return result
    
            c = node.getChild(i)
            if isinstance(c, RosMessageParser.Rosbag_nested_messageContext):
                childResult = c.accept(self)
                nested_message_identifier = struct_name[c.getChild(1).getChild(2).getText()]
                result = self.aggregateStruct(result, childResult, nested_message_identifier)
    
        return result

    def aggregateStruct(self, aggregate, nextResult, nested_message_identifier):
        return aggregate.add(nested_message_identifier, nextResult, True)

    def aggregateFieldNames(self, aggregate, nextResult):
        aggregate.append(nextResult)
        return aggregate

    def visitRosbag_nested_message(self, ctx):
        return self.visitRosMessageChildren(ctx)
    
    def aggregateFieldNames(self, aggregate, nextResult):
        aggregate.append(nextResult)
        return aggregate

    def visitRosMessageChildren(self, node):
        result = self.defaultResult()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return result
    
            c = node.getChild(i)
            if isinstance(c, RosMessageParser.Ros_messageContext):
                childResult = c.accept(self)
                result = self.aggregateResult(result, childResult)
    
        return result
    
    def visitRos_message(self, ctx):
        return self.visitFieldDeclarationStructChildren(ctx)

    def visitFieldDeclarationStructChildren(self, node):
        result = StructType()
        n = node.getChildCount()
        for i in range(n):
            if not self.shouldVisitNextChild(node, result):
                return result
    
            c = node.getChild(i)
            if isinstance(c, RosMessageParser.Field_declarationContext):
                childResult = c.accept(self)
                result = self.aggregateField(result, childResult)
    
        return result
    
    def aggregateField(self, aggregate, nextResult):
        ros_type = nextResult.keys()[0]
        ros_fieldname = nextResult.values()[0]

        if ros_fieldname == 'stamp' and ros_type == 'time':
            stamp = StructType()
            stamp.add('sec', 'integer', True)
            stamp.add('nsec', 'integer', True)
            aggregate.add('stamp', stamp , True)
        else:
            aggregate.add(ros_fieldname, self._convert_to_spark_type(ros_type) , True)

        return aggregate
    
    def _convert_to_spark_type(self, ros_type):
        ros_type_to_pyspark_map = {
            'bool': 'boolean',
            'int8': 'integer',
            'uint8': 'integer',
            'int16': 'integer',
            'uint16': 'integer',
            'int32': 'integer',
            'uint32': 'integer',
            'int64': 'long',
            'uint64': 'long',
            'float32': 'float',
            'float64': 'float',
            'string': 'string'
        }

        if (self._is_ros_binary_type(ros_type)):
            return 'binary'
        else:
            return ros_type_to_pyspark_map[ros_type]

    def _is_ros_binary_type(self, ros_type):
        ros_binary_types_regexp = re.compile(r'(uint8|char)\[[^\]]*\]')

        return re.search(ros_binary_types_regexp, ros_type) is not None
