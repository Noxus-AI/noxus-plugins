"""Test suite for linear plugin"""

import pytest
from linear import LinearPlugin
from linear.nodes import (
    LinearIssuesReaderNode,
)


def test_plugin_initialization():
    """Test that the plugin can be initialized"""
    plugin = LinearPlugin()
    assert plugin.name == "linear"
    assert plugin.version == "0.1.0"
    assert "Linear integration" in plugin.description


def test_plugin_nodes():
    """Test that the node is available"""
    plugin = LinearPlugin()
    nodes = plugin.nodes()
    
    expected_nodes = [
        LinearIssuesReaderNode,
    ]
    
    assert len(nodes) == len(expected_nodes)
    for node in expected_nodes:
        assert node in nodes


def test_node_properties():
    """Test basic properties of the node"""
    assert LinearIssuesReaderNode.node_name == "LinearIssuesReaderNode"
    assert LinearIssuesReaderNode.title == "Fetch Linear issues"
    assert "linear" in LinearIssuesReaderNode.integrations


def test_node_category():
    """Test that the node has correct category"""
    from spotflow.nodes.base import NodeCategory
    
    assert LinearIssuesReaderNode.category == NodeCategory.Integrations
    assert LinearIssuesReaderNode.sub_category == "Linear"


def test_node_outputs():
    """Test that the node has the expected outputs"""
    assert len(LinearIssuesReaderNode.outputs) == 1
    assert LinearIssuesReaderNode.outputs[0].name == "issues"
